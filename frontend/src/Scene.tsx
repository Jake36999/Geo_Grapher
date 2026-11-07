import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { Vec3, ViewportFrameData } from "../../contracts/geographer.wire";
import { shortName, type Node } from "./api";
import { samples, type Lens } from "./curves";
import {
  editedScene,
  editSelection,
  selectionRoots,
  descendants,
  type Affine,
} from "./layoutEditing";

export interface CameraState {
  eye: Vec3;
  target: Vec3;
}
export interface SceneHandle {
  capture: () => CameraState | undefined;
  fit: () => void;
  zoom: (factor: number) => void;
}
export type SceneData = Pick<
  ViewportFrameData,
  "nodes" | "relationships" | "spheres" | "curves"
>;
interface Props {
  frame?: SceneData;
  declaredLinks?: {
    id: string;
    source: Vec3;
    target: Vec3;
    sourceNodeId?: string;
    targetNodeId?: string;
  }[];
  focusId: string;
  navigationKey: string;
  selectedId: string;
  selectedEdge: string;
  highlightedEdges?: string[];
  violations?: string[];
  beta: number;
  lensEnabled: boolean;
  theme: "dark" | "light";
  initialCamera?: CameraState;
  onPick: (
    ids: string[],
    position: { x: number; y: number },
    edge?: boolean,
  ) => void;
  onEnter: (id: string) => void;
  onFailure: (reason: string) => void;
}

type Bucket = { mesh: THREE.InstancedMesh; capacity: number; ids: string[] };
type DebugMetrics = {
  frames: number;
  fps: number[];
  drawCalls: number;
  triangles: number;
  geometries: number;
  textures: number;
  renderer: string;
  nodeCount: number;
  curveCount: number;
};
declare global {
  interface Window {
    __geographerMetrics?: DebugMetrics;
  }
}

export default forwardRef<SceneHandle, Props>(function Scene(props, ref) {
  const host = useRef<HTMLDivElement>(null),
    propsRef = useRef(props),
    controller = useRef<
      | {
          capture: () => CameraState;
          fit: () => void;
          zoom: (f: number) => void;
          update: () => void;
          resetLayout: () => void;
          scaleSelection: (factor: number) => void;
          moveSelection: (dx: number, dy: number) => void;
        }
      | undefined
    >(undefined);
  const [failure, setFailure] = useState("");
  const [boxMode, setBoxMode] = useState(false),
    [editCount, setEditCount] = useState(0);
  const modeRef = useRef(false);
  modeRef.current = boxMode;
  propsRef.current = props;
  useImperativeHandle(
    ref,
    () => ({
      capture: () => controller.current?.capture(),
      fit: () => controller.current?.fit(),
      zoom: (f) => controller.current?.zoom(f),
    }),
    [],
  );
  useEffect(() => {
    const element = host.current!;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        powerPreference: "high-performance",
      });
    } catch {
      const reason =
        "Spatial rendering is unavailable. The hierarchy and dependency matrix remain available.";
      setFailure(reason);
      propsRef.current.onFailure(reason);
      return;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    element.prepend(renderer.domElement);
    renderer.domElement.setAttribute("aria-hidden", "true");
    renderer.domElement.dataset.testid = "architecture-canvas";
    const scene = new THREE.Scene(),
      camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000000);
    camera.position.set(20, 14, 26);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.09;
    const edits = new Map<string, Affine>();
    let sceneRevision = 0;
    let displayData: SceneData | undefined,
      selection: string[] = [];
    let layoutNavigation = propsRef.current.navigationKey;
    const marquee = document.createElement("div");
    marquee.className = "scene-marquee";
    marquee.hidden = true;
    element.append(marquee);
    const groupBox = document.createElement("div");
    groupBox.className = "scene-group-box";
    groupBox.dataset.testid = "layout-selection";
    groupBox.hidden = true;
    element.append(groupBox);
    controls.maxPolarAngle = Math.PI - 0.02;
    controls.minPolarAngle = 0.02;
    scene.add(new THREE.AmbientLight(0xffffff, 1.8));
    const key = new THREE.DirectionalLight(0xffffff, 2);
    key.position.set(10, 15, 20);
    scene.add(key);
    const sphereGeometry = new THREE.SphereGeometry(1, 24, 16);
    const shellMaterial = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      side: THREE.BackSide,
      uniforms: { strength: { value: 1 } },
      vertexShader: `varying vec3 shellNormal;varying vec3 shellView;varying vec3 shellColor;
        void main(){vec4 mv=modelViewMatrix*instanceMatrix*vec4(position,1.0);shellNormal=normalize(normalMatrix*mat3(instanceMatrix)*normal);
        shellView=-mv.xyz;shellColor=instanceColor;gl_Position=projectionMatrix*mv;}`,
      fragmentShader: `uniform float strength;varying vec3 shellNormal;varying vec3 shellView;varying vec3 shellColor;
        void main(){float rim=pow(1.0-abs(dot(normalize(shellNormal),normalize(shellView))),3.0);
        gl_FragColor=vec4(shellColor,strength*(0.025+0.7*rim));
        #include <colorspace_fragment>
        }`,
    });
    const materials = {
      context: new THREE.MeshBasicMaterial({
        color: 0xa8adb4,
        transparent: true,
        opacity: 0.045,
        depthWrite: false,
        side: THREE.BackSide,
      }),
      container: shellMaterial,
      core: new THREE.MeshStandardMaterial({
        color: 0xffffff,
        roughness: 0.9,
        metalness: 0,
        transparent: true,
        opacity: 0.9,
      }),
    };
    const buckets: Record<string, Bucket> = {};
    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0xffffff,
      vertexColors: true,
      transparent: true,
      opacity: 0.42,
      depthWrite: false,
    });
    const lines = new THREE.LineSegments(
      new THREE.BufferGeometry(),
      lineMaterial,
    );
    scene.add(lines);
    // Operator assertions use a separate display layer, never dependency rows.
    const declaredLayer = new THREE.Group();
    const declaredMaterial = new THREE.LineDashedMaterial({
      color: 0xd5b27b,
      dashSize: 0.16,
      gapSize: 0.1,
      transparent: true,
      opacity: 0.8,
    });
    scene.add(declaredLayer);
    function updateDeclaredLinks() {
      for (const object of [...declaredLayer.children]) {
        (object as THREE.Line).geometry.dispose();
        declaredLayer.remove(object);
      }
      for (const [index, link] of (
        propsRef.current.declaredLinks ?? []
      ).entries()) {
        const a = new THREE.Vector3(
            ...(spheres.get(link.sourceNodeId ?? "")?.center ?? link.source),
          ),
          b = new THREE.Vector3(
            ...(spheres.get(link.targetNodeId ?? "")?.center ?? link.target),
          );
        const mid = a.clone().lerp(b, 0.5);
        mid.y += 1.5 + index * 0.08;
        const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(curve.getPoints(48)),
          declaredMaterial,
        );
        line.userData.declared_bridge_id = link.id;
        line.computeLineDistances();
        declaredLayer.add(line);
      }
    }
    const selectedMaterial = new THREE.LineBasicMaterial({
      color: 0xa7bccd,
      transparent: true,
      opacity: 0.95,
      depthTest: false,
    });
    const selectedLine = new THREE.LineSegments(
      new THREE.BufferGeometry(),
      selectedMaterial,
    );
    selectedLine.renderOrder = 20;
    scene.add(selectedLine);
    const ringGeometry = new THREE.BufferGeometry().setFromPoints(
      Array.from(
        { length: 96 },
        (_, i) =>
          new THREE.Vector3(
            Math.cos((i / 96) * Math.PI * 2),
            Math.sin((i / 96) * Math.PI * 2),
            0,
          ),
      ),
    );
    const ring = new THREE.LineLoop(ringGeometry, selectedMaterial);
    ring.renderOrder = 21;
    scene.add(ring);
    const hoverRings = [
      new THREE.LineLoop(ringGeometry, selectedMaterial),
      new THREE.LineLoop(ringGeometry, selectedMaterial),
    ];
    for (const mark of hoverRings) {
      mark.visible = false;
      mark.renderOrder = 22;
      scene.add(mark);
    }
    const arrow = new THREE.ArrowHelper(
      new THREE.Vector3(0, 1, 0),
      new THREE.Vector3(),
      1,
      0xa7bccd,
    );
    arrow.visible = false;
    scene.add(arrow);
    const labelLayer = document.createElement("div");
    labelLayer.className = "scene-labels";
    labelLayer.setAttribute("aria-hidden", "true");
    element.append(labelLayer);
    const labels = new Map<string, HTMLDivElement>();
    let nodes = new Map<string, Node>(),
      spheres = new Map<string, ViewportFrameData["spheres"][number]>();
    let relationLookup = new Map<
      string,
      ViewportFrameData["relationships"][number]
    >();
    let edgePoints = new Map<string, Vec3[]>(),
      segmentIds: string[] = [],
      lastNavigation = "",
      hasFramed = false;
    let frameId = 0,
      disposed = false,
      lastTime = performance.now(),
      lastLens = 0,
      lineCapacity = 0;
    let tween:
      | {
          start: number;
          fromEye: THREE.Vector3;
          fromTarget: THREE.Vector3;
          eye: THREE.Vector3;
          target: THREE.Vector3;
        }
      | undefined;
    let currentLens: Lens = {
      enabled: false,
      center: [0, 0, 0],
      radius: 5,
      strength: 0.8,
    };
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    const ray = new THREE.Raycaster(),
      pointer = new THREE.Vector2(),
      matrix = new THREE.Matrix4(),
      color = new THREE.Color();
    const screen = new THREE.Vector3();
    const metrics: DebugMetrics = {
      frames: 0,
      fps: [],
      drawCalls: 0,
      triangles: 0,
      geometries: 0,
      textures: 0,
      renderer: "unknown",
      nodeCount: 0,
      curveCount: 0,
    };
    if (new URLSearchParams(location.search).has("debug")) {
      const gl = renderer.getContext(),
        ext = gl.getExtension("WEBGL_debug_renderer_info");
      metrics.renderer = ext
        ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)
        : "WebGL";
      window.__geographerMetrics = metrics;
    }
    function capture(): CameraState {
      return {
        eye: camera.position.toArray() as Vec3,
        target: controls.target.toArray() as Vec3,
      };
    }
    function fit() {
      const id = propsRef.current.focusId;
      let sphere = spheres.get(id);
      if (!id && spheres.size) {
        const bounds = new THREE.Box3();
        for (const value of spheres.values()) {
          if (nodes.get(value.node_id)?.kind === "workspace") continue;
          bounds.expandByPoint(
            new THREE.Vector3(...value.center).addScalar(value.radius),
          );
          bounds.expandByPoint(
            new THREE.Vector3(...value.center).addScalar(-value.radius),
          );
        }
        if (bounds.isEmpty()) return;
        const enclosing = bounds.getBoundingSphere(new THREE.Sphere());
        sphere = {
          node_id: "display-enclosure",
          center: enclosing.center.toArray() as Vec3,
          radius: enclosing.radius,
          role: "context_shell",
        };
      }
      if (!sphere) return;
      const halfVertical = (camera.fov * Math.PI) / 360,
        half = Math.min(
          halfVertical,
          Math.atan(Math.tan(halfVertical) * camera.aspect),
        );
      const target = new THREE.Vector3(...sphere.center),
        distance = (sphere.radius / Math.sin(half)) * 1.25;
      const direction = new THREE.Vector3(1.25, 0.72, 1.55).normalize(),
        eye = target.clone().addScaledVector(direction, distance);
      camera.near = Math.max(0.001, sphere.radius / 1000);
      camera.far = Math.max(10000, distance * 1000);
      camera.updateProjectionMatrix();
      if (reduced.matches) {
        camera.position.copy(eye);
        controls.target.copy(target);
        controls.update();
        tween = undefined;
      } else
        tween = {
          start: performance.now(),
          fromEye: camera.position.clone(),
          fromTarget: controls.target.clone(),
          eye,
          target,
        };
    }
    controls.addEventListener("start", () => {
      tween = undefined;
    });
    let hoverEdge = "",
      hoverNode = "",
      lastHover = 0;
    const tooltip = document.createElement("div");
    tooltip.className = "scene-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.hidden = true;
    element.append(tooltip);
    function dotted(id: string) {
      const status = relationLookup.get(id)?.resolution_status;
      return status === "candidate" || status === "unresolved";
    }
    function segmentVisible(id: string, index: number) {
      const relation = relationLookup.get(id);
      if (dotted(id)) return index % 2 === 0;
      if (relation?.family === "expected") return index % 6 < 4;
      if (
        relation?.subtype === "imports" ||
        relation?.subtype === "imports_from"
      )
        return index % 8 < 6;
      if (relation?.subtype === "inherits")
        return [0, 1, 3, 4].includes(index % 8);
      return true;
    }
    function updateEdges() {
      const data = displayData;
      if (!data) return;
      relationLookup = new Map(data.relationships.map((r) => [r.id, r]));
      const selected =
        spheres.get(propsRef.current.selectedId) ??
        spheres.get(propsRef.current.focusId);
      if (selected && !currentLens.enabled)
        currentLens.center = [...selected.center];
      currentLens = {
        ...currentLens,
        enabled: propsRef.current.lensEnabled,
        radius: selected ? 3 * selected.radius : 5,
      };
      edgePoints = new Map();
      segmentIds = [];
      let segmentCount = 0;
      for (const curve of data.curves) {
        const points = samples(
          curve,
          propsRef.current.beta,
          currentLens,
          spheres.get(curve.canonical_source)?.radius ?? 1,
        );
        edgePoints.set(curve.relationship_id, points);
        segmentCount += points.length - 1;
      }
      const needed = segmentCount * 6;
      if (needed > lineCapacity) {
        // Round the number of vertices, then allocate three floats per vertex.
        // A power-of-two float count leaves a partial xyz tuple, which poisons
        // Three.js bounding spheres with undefined/NaN coordinates.
        lineCapacity = 3 * 2 ** Math.ceil(Math.log2(Math.max(2, needed / 3)));
        lines.geometry.dispose();
        lines.geometry = new THREE.BufferGeometry();
        lines.geometry.setAttribute(
          "position",
          new THREE.BufferAttribute(new Float32Array(lineCapacity), 3),
        );
        lines.geometry.setAttribute(
          "color",
          new THREE.BufferAttribute(new Float32Array(lineCapacity), 3),
        );
      }
      const positions = lines.geometry.getAttribute("position") as
        THREE.BufferAttribute | undefined;
      const colors = lines.geometry.getAttribute("color") as
        THREE.BufferAttribute | undefined;
      let offset = 0;
      if (positions) {
        for (const [id, points] of edgePoints) {
          const relation = relationLookup.get(id),
            highlight = propsRef.current.highlightedEdges?.includes(id);
          const color = new THREE.Color(
            highlight
              ? "#A7BCCD"
              : propsRef.current.violations?.includes(id)
                ? "#D5B27B"
                : relation?.family === "runtime"
                  ? "#9FB7AC"
                  : propsRef.current.theme === "light"
                    ? "#5C646E"
                    : "#A8ADB4",
          );
          for (let i = 0; i < points.length - 1; i++) {
            if (!segmentVisible(id, i)) continue;
            positions.setXYZ(offset / 3, ...points[i]);
            const from = color
              .clone()
              .multiplyScalar(0.65 + (0.35 * i) / (points.length - 1));
            colors?.setXYZ(offset / 3, from.r, from.g, from.b);
            offset += 3;
            positions.setXYZ(offset / 3, ...points[i + 1]);
            const to = color
              .clone()
              .multiplyScalar(0.65 + (0.35 * (i + 1)) / (points.length - 1));
            colors?.setXYZ(offset / 3, to.r, to.g, to.b);
            offset += 3;
            segmentIds.push(id);
          }
        }
        positions.needsUpdate = true;
        if (colors) colors.needsUpdate = true;
        lines.geometry.setDrawRange(0, segmentIds.length * 2);
        lines.geometry.computeBoundingSphere();
      }
      updateSelection();
    }
    function updateSelection() {
      const p = propsRef.current,
        selected = spheres.get(p.selectedId);
      const hoveredRelation = relationLookup.get(hoverEdge),
        hoverIds = hoveredRelation
          ? [hoveredRelation.source, hoveredRelation.target]
          : hoverNode
            ? [hoverNode]
            : [];
      hoverRings.forEach((mark, i) => {
        const s = spheres.get(hoverIds[i]);
        mark.visible = Boolean(s);
        if (s) {
          mark.position.set(...s.center);
          mark.scale.setScalar(s.radius * 1.07);
        }
      });
      ring.visible = Boolean(selected);
      if (selected) {
        ring.position.set(...selected.center);
        ring.scale.setScalar(selected.radius * 1.035);
      }
      const activeEdge = hoverEdge || p.selectedEdge;
      const points = edgePoints.get(activeEdge);
      selectedLine.visible = Boolean(points);
      arrow.visible = Boolean(points && points.length > 1);
      if (points) {
        selectedLine.geometry.dispose();
        selectedLine.geometry = new THREE.BufferGeometry().setFromPoints(
          points
            .slice(0, -1)
            .flatMap((v, i) =>
              !segmentVisible(activeEdge, i)
                ? []
                : [
                    new THREE.Vector3(...v),
                    new THREE.Vector3(...points[i + 1]),
                  ],
            ),
        );
        const i = Math.min(points.length - 2, Math.floor(points.length * 0.76)),
          start = new THREE.Vector3(...points[i]),
          direction = new THREE.Vector3(...points[i + 1])
            .sub(start)
            .normalize();
        const scale = Math.max(
          0.12,
          (spheres.get(p.focusId)?.radius ?? 2) * 0.035,
        );
        arrow.position.copy(start);
        arrow.setDirection(direction);
        arrow.setLength(scale * 2, scale, scale * 0.55);
      }
    }
    function update() {
      const p = propsRef.current;
      if (layoutNavigation !== p.navigationKey) {
        edits.clear();
        selection = [];
        setEditCount(0);
        layoutNavigation = p.navigationKey;
      }
      const data = p.frame ? editedScene(p.frame, edits) : undefined;
      if (!data) return;
      displayData = data;
      scene.background = new THREE.Color(
        p.theme === "dark" ? 0x17191c : 0xf3f2ef,
      );
      lineMaterial.opacity = p.theme === "dark" ? 0.65 : 0.85;
      lineMaterial.color.set(0xffffff);
      selectedMaterial.color.set(p.theme === "dark" ? 0xa7bccd : 0x385d76);
      arrow.setColor(selectedMaterial.color);
      nodes = new Map(data.nodes.map((n) => [n.id, n]));
      spheres = new Map(data.spheres.map((s) => [s.node_id, s]));
      const byBucket: Record<string, typeof data.spheres> = {
        context: [],
        container: [],
        core: [],
      };
      for (const s of data.spheres) {
        const n = nodes.get(s.node_id);
        // Workspace is a virtual packing frame; each repository is a separate
        // visible root cluster, never a child of the first imported project.
        if (n?.kind === "workspace") continue;
        const type =
          s.role === "context_shell"
            ? "context"
            : n &&
                [
                  "function",
                  "method",
                  "scope_atom",
                  "external_symbol",
                ].includes(n.kind)
              ? "core"
              : "container";
        byBucket[type].push(s);
      }
      const palette =
        p.theme === "dark"
          ? [0xa7b4bc, 0xaaa69a, 0x9faea3, 0xaca6af]
          : [0x627783, 0x817c6f, 0x708477, 0x847a88];
      for (const [kind, values] of Object.entries(byBucket)) {
        let bucket = buckets[kind];
        if (!bucket || values.length > bucket.capacity) {
          if (bucket) {
            scene.remove(bucket.mesh);
            bucket.mesh.dispose();
          }
          const capacity = Math.max(
            1,
            2 ** Math.ceil(Math.log2(Math.max(1, values.length))),
          );
          const mesh = new THREE.InstancedMesh(
            sphereGeometry,
            materials[kind as keyof typeof materials],
            capacity,
          );
          mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
          scene.add(mesh);
          bucket = buckets[kind] = { mesh, capacity, ids: [] };
        }
        bucket.ids = values.map((s) => s.node_id);
        bucket.mesh.count = values.length;
        values.forEach((s, i) => {
          matrix.makeScale(s.radius, s.radius, s.radius);
          matrix.setPosition(...s.center);
          bucket.mesh.setMatrixAt(i, matrix);
          const n = nodes.get(s.node_id);
          const hash = Array.from(n?.parent_id ?? s.node_id).reduce(
            (a, c) => a + c.charCodeAt(0),
            0,
          );
          color.setHex(
            selection.includes(s.node_id)
              ? 0xa7bccd
              : palette[hash % palette.length],
          );
          bucket.mesh.setColorAt(i, color);
        });
        bucket.mesh.instanceMatrix.needsUpdate = true;
        if (bucket.mesh.instanceColor)
          bucket.mesh.instanceColor.needsUpdate = true;
        bucket.mesh.computeBoundingSphere();
      }
      const labelIds = new Set(
        [...data.spheres]
          .filter((s) => nodes.get(s.node_id)?.kind !== "workspace")
          .sort((a, b) => {
            const priority = (id: string) =>
              id === p.selectedId
                ? 0
                : id === p.focusId
                  ? 1
                  : nodes.get(id)?.kind === "residual"
                    ? 4
                    : 2;
            return (
              priority(a.node_id) - priority(b.node_id) ||
              a.node_id.localeCompare(b.node_id)
            );
          })
          .slice(0, 45)
          .map((s) => s.node_id),
      );
      for (const [id, label] of labels)
        if (!labelIds.has(id)) {
          label.remove();
          labels.delete(id);
        }
      for (const id of labelIds) {
        let label = labels.get(id);
        if (!label) {
          label = document.createElement("div");
          label.className = "scene-node-label";
          label.style.opacity = "0";
          labelLayer.append(label);
          labels.set(id, label);
        }
        const n = nodes.get(id);
        label.textContent = n ? shortName(n) : id;
        label.dataset.selected = String(id === p.selectedId);
      }
      updateEdges();
      updateDeclaredLinks();
      metrics.nodeCount = data.spheres.length;
      metrics.curveCount = data.curves.length;
      if (spheres.size && (!hasFramed || lastNavigation !== p.navigationKey)) {
        if (p.initialCamera) {
          camera.position.set(...p.initialCamera.eye);
          controls.target.set(...p.initialCamera.target);
          controls.update();
        } else fit();
        hasFramed = true;
        lastNavigation = p.navigationKey;
      }
      renderer.domElement.dataset.layoutRevision = String(++sceneRevision);
    }
    controller.current = {
      capture,
      fit,
      resetLayout: () => {
        edits.clear();
        selection = [];
        setEditCount(0);
        update();
      },
      scaleSelection: (factor) => manipulate(factor, [0, 0, 0]),
      moveSelection: (dx, dy) => {
        const pivot = selectionPivot(),
          step =
            camera.position.distanceTo(new THREE.Vector3(...pivot)) * 0.025;
        const right = new THREE.Vector3().setFromMatrixColumn(
          camera.matrixWorld,
          0,
        );
        const up = new THREE.Vector3().setFromMatrixColumn(
          camera.matrixWorld,
          1,
        );
        manipulate(
          1,
          right
            .multiplyScalar(dx * step)
            .addScaledVector(up, dy * step)
            .toArray() as Vec3,
        );
      },
      zoom: (factor) => {
        camera.position
          .sub(controls.target)
          .multiplyScalar(factor)
          .add(controls.target);
        controls.update();
      },
      update,
    };
    const resize = new ResizeObserver(() => {
      const width = element.clientWidth,
        height = element.clientHeight;
      if (!width || !height) return;
      const tools = element.querySelector<HTMLElement>(".scene-layout-tools");
      element.parentElement?.style.setProperty(
        "--layout-tools-bottom",
        `${(tools?.offsetHeight ?? 30) + 20}px`,
      );
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    });
    resize.observe(element);
    const layoutTools = element.querySelector(".scene-layout-tools");
    if (layoutTools) resize.observe(layoutTools);
    let down = { x: 0, y: 0 };
    function intersect(event: PointerEvent, containers = false) {
      const box = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((event.clientX - box.left) / box.width) * 2 - 1,
        (-(event.clientY - box.top) / box.height) * 2 + 1,
      );
      ray.setFromCamera(pointer, camera);
      const meshes = Object.entries(buckets)
        .filter(([kind]) => containers || kind !== "context")
        .map(([, b]) => b.mesh);
      return ray.intersectObjects(meshes, false);
    }
    function projected(id: string) {
      const s = spheres.get(id);
      if (!s || nodes.get(id)?.kind === "workspace") return;
      const box = renderer.domElement.getBoundingClientRect();
      const centre = new THREE.Vector3(...s.center),
        p = centre.clone().project(camera);
      if (p.z < -1 || p.z > 1) return;
      const edge = centre
        .clone()
        .addScaledVector(
          new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0),
          s.radius,
        )
        .project(camera);
      return {
        id,
        x: box.left + ((p.x + 1) * box.width) / 2,
        y: box.top + ((1 - p.y) * box.height) / 2,
        r: (Math.abs(edge.x - p.x) * box.width) / 2,
      };
    }
    function selectionPivot(): Vec3 {
      const bounds = new THREE.Box3();
      for (const id of selection) {
        const s = spheres.get(id);
        if (!s) continue;
        bounds.expandByPoint(
          new THREE.Vector3(...s.center).addScalar(s.radius),
        );
        bounds.expandByPoint(
          new THREE.Vector3(...s.center).addScalar(-s.radius),
        );
      }
      return bounds.isEmpty()
        ? [0, 0, 0]
        : (bounds.getCenter(new THREE.Vector3()).toArray() as Vec3);
    }
    function manipulate(factor: number, delta: Vec3) {
      if (!propsRef.current.frame || !selection.length) return;
      editSelection(
        propsRef.current.frame,
        edits,
        selection,
        selectionPivot(),
        factor,
        delta,
      );
      update();
    }
    function setSelection(ids: string[]) {
      selection = propsRef.current.frame
        ? selectionRoots(propsRef.current.frame, ids)
        : [];
      setEditCount(selection.length);
      update();
    }
    function drawBox(
      div: HTMLDivElement,
      left: number,
      top: number,
      right: number,
      bottom: number,
    ) {
      const box = element.getBoundingClientRect();
      div.hidden = false;
      Object.assign(div.style, {
        left: `${left - box.left}px`,
        top: `${top - box.top}px`,
        width: `${Math.max(1, right - left)}px`,
        height: `${Math.max(1, bottom - top)}px`,
      });
    }
    function drawSelection() {
      const values = selection
        .map(projected)
        .filter((p): p is NonNullable<typeof p> => Boolean(p));
      if (!values.length) {
        groupBox.hidden = true;
        return;
      }
      drawBox(
        groupBox,
        Math.min(...values.map((p) => p.x - p.r)) - 6,
        Math.min(...values.map((p) => p.y - p.r)) - 6,
        Math.max(...values.map((p) => p.x + p.r)) + 6,
        Math.max(...values.map((p) => p.y + p.r)) + 6,
      );
    }
    type Gesture = {
      kind: "move" | "box";
      pointerId: number;
      x: number;
      y: number;
      last: THREE.Vector3 | null;
      plane: THREE.Plane;
      changed: boolean;
      before: Map<string, Affine>;
    };
    let gesture: Gesture | undefined;
    const canvas = renderer.domElement;
    canvas.removeAttribute("aria-hidden");
    canvas.tabIndex = 0;
    canvas.setAttribute("role", "img");
    canvas.setAttribute(
      "aria-label",
      "Architecture canvas. Shift-drag to box select; hold a bubble edge to move or wheel to resize.",
    );
    groupBox.setAttribute("aria-label", "Selected nodes");
    groupBox.setAttribute("role", "img");
    function rayPoint(e: PointerEvent, plane: THREE.Plane) {
      const b = canvas.getBoundingClientRect();
      ray.setFromCamera(
        new THREE.Vector2(
          ((e.clientX - b.left) / b.width) * 2 - 1,
          1 - ((e.clientY - b.top) / b.height) * 2,
        ),
        camera,
      );
      return ray.ray.intersectPlane(plane, new THREE.Vector3());
    }
    const startEdit = (e: PointerEvent) => {
      if (e.button !== 0 || !displayData) return;
      camera.updateMatrixWorld();
      const rims = [...spheres.keys()]
        .map(projected)
        .filter((p): p is NonNullable<typeof p> =>
          Boolean(
            p &&
            p.r >= 10 &&
            Math.abs(Math.hypot(e.clientX - p.x, e.clientY - p.y) - p.r) <=
              Math.min(8, p.r * 0.18),
          ),
        )
        .sort(
          (a, b) =>
            Math.abs(Math.hypot(e.clientX - a.x, e.clientY - a.y) - a.r) -
            Math.abs(Math.hypot(e.clientX - b.x, e.clientY - b.y) - b.r),
        );
      const box = groupBox.getBoundingClientRect();
      const inGroup =
        !groupBox.hidden &&
        e.clientX >= box.left &&
        e.clientX <= box.right &&
        e.clientY >= box.top &&
        e.clientY <= box.bottom;
      let kind: "move" | "box";
      if (e.shiftKey) kind = "box";
      else if (rims.length) {
        if (!descendants(displayData, selection).has(rims[0].id))
          setSelection([rims[0].id]);
        kind = "move";
      } else if (inGroup && selection.length) kind = "move";
      else if (modeRef.current) kind = "box";
      else return;
      e.preventDefault();
      e.stopImmediatePropagation();
      canvas.focus({ preventScroll: true });
      controls.enabled = false;
      tween = undefined;
      const pivot = selectionPivot(),
        plane = new THREE.Plane().setFromNormalAndCoplanarPoint(
          camera.getWorldDirection(new THREE.Vector3()),
          new THREE.Vector3(...pivot),
        );
      gesture = {
        kind,
        pointerId: e.pointerId,
        x: e.clientX,
        y: e.clientY,
        last: rayPoint(e, plane),
        plane,
        changed: false,
        before: new Map(edits),
      };
      canvas.setPointerCapture(e.pointerId);
      if (kind === "box")
        drawBox(marquee, e.clientX, e.clientY, e.clientX, e.clientY);
    };
    const dragEdit = (e: PointerEvent) => {
      if (!gesture) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      if (gesture.kind === "box")
        drawBox(
          marquee,
          Math.min(e.clientX, gesture.x),
          Math.min(e.clientY, gesture.y),
          Math.max(e.clientX, gesture.x),
          Math.max(e.clientY, gesture.y),
        );
      else {
        const value = rayPoint(e, gesture.plane);
        if (value && gesture.last) {
          const delta = value.clone().sub(gesture.last);
          if (delta.length() > 1e-8) {
            manipulate(1, delta.toArray() as Vec3);
            gesture.changed = true;
          }
        }
        gesture.last = value;
      }
    };
    const endEdit = (e: PointerEvent) => {
      if (!gesture) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      if (gesture.kind === "box" && e.type !== "pointercancel") {
        const left = Math.min(e.clientX, gesture.x),
          right = Math.max(e.clientX, gesture.x),
          top = Math.min(e.clientY, gesture.y),
          bottom = Math.max(e.clientY, gesture.y);
        const candidates = [...spheres.values()]
          .filter((s) => s.role !== "context_shell")
          .map((s) => projected(s.node_id))
          .filter(
            (p) =>
              p && p.x >= left && p.x <= right && p.y >= top && p.y <= bottom,
          )
          .map((p) => p!.id);
        setSelection(candidates);
      } else if (
        !gesture.changed &&
        selection.length === 1 &&
        e.type !== "pointercancel"
      )
        propsRef.current.onPick(selection, { x: e.clientX, y: e.clientY });
      gesture = undefined;
      marquee.hidden = true;
      controls.enabled = true;
      if (canvas.hasPointerCapture(e.pointerId))
        canvas.releasePointerCapture(e.pointerId);
    };
    const resizeEdit = (e: WheelEvent) => {
      if (gesture?.kind !== "move") return;
      e.preventDefault();
      e.stopImmediatePropagation();
      const delta =
        e.deltaY *
        (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? element.clientHeight : 1);
      manipulate(
        Math.exp(-Math.max(-400, Math.min(400, delta)) * 0.0015),
        [0, 0, 0],
      );
      gesture.changed = true;
    };
    const cancelEdit = (e: KeyboardEvent) => {
      if (
        e.key !== "Escape" ||
        !(gesture || element.contains(document.activeElement))
      )
        return;
      if (gesture) {
        const cancelled = gesture;
        gesture = undefined;
        edits.clear();
        for (const [id, value] of cancelled.before) edits.set(id, value);
        if (canvas.hasPointerCapture(cancelled.pointerId))
          canvas.releasePointerCapture(cancelled.pointerId);
      }
      gesture = undefined;
      marquee.hidden = true;
      controls.enabled = true;
      setSelection([]);
      e.preventDefault();
    };
    const pointerDown = (e: PointerEvent) => {
      down = { x: e.clientX, y: e.clientY };
    };
    const pointerUp = (e: PointerEvent) => {
      if (Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) return;
      const ids = [
        ...new Set(
          intersect(e, e.altKey)
            .map(
              (hit) =>
                Object.values(buckets).find((b) => b.mesh === hit.object)?.ids[
                  hit.instanceId ?? -1
                ],
            )
            .filter((id): id is string => Boolean(id)),
        ),
      ];
      if (ids.length) {
        propsRef.current.onPick(ids, { x: e.clientX, y: e.clientY });
        return;
      }
      const height = Math.max(1, element.clientHeight);
      ray.params.Line.threshold =
        (camera.position.distanceTo(controls.target) *
          Math.tan((camera.fov * Math.PI) / 360) *
          8) /
        height;
      const hits = ray.intersectObject(lines);
      const edges = [
        ...new Set(
          hits
            .map((hit) => segmentIds[Math.floor((hit.index ?? 0) / 2)])
            .filter(Boolean),
        ),
      ];
      if (edges.length)
        propsRef.current.onPick(edges, { x: e.clientX, y: e.clientY }, true);
    };
    const doubleClick = (e: MouseEvent) => {
      const ids = [
        ...new Set(
          intersect(e as PointerEvent)
            .map(
              (hit) =>
                Object.values(buckets).find((b) => b.mesh === hit.object)?.ids[
                  hit.instanceId ?? -1
                ],
            )
            .filter((id): id is string => Boolean(id)),
        ),
      ];
      if (ids.length === 1) propsRef.current.onEnter(ids[0]);
      else if (ids.length)
        propsRef.current.onPick(ids, { x: e.clientX, y: e.clientY });
    };
    const move = (e: PointerEvent) => {
      if (performance.now() - lastHover < 80 || e.buttons) return;
      lastHover = performance.now();
      const hit = intersect(e)[0];
      let text = "";
      hoverEdge = "";
      hoverNode = "";
      if (hit) {
        const bucket = Object.values(buckets).find(
            (b) => b.mesh === hit.object,
          ),
          id = bucket?.ids[hit.instanceId ?? -1];
        hoverNode = id ?? "";
        text = id ? (nodes.get(id)?.qualified_name ?? id) : "";
      } else {
        ray.params.Line.threshold =
          (camera.position.distanceTo(controls.target) *
            Math.tan((camera.fov * Math.PI) / 360) *
            8) /
          Math.max(1, element.clientHeight);
        const edge = ray.intersectObject(lines)[0];
        hoverEdge = edge
          ? (segmentIds[Math.floor((edge.index ?? 0) / 2)] ?? "")
          : "";
        const r = propsRef.current.frame?.relationships.find(
          (r) => r.id === hoverEdge,
        );
        if (r)
          text = `${nodes.get(r.source)?.qualified_name ?? r.source} → ${nodes.get(r.target)?.qualified_name ?? r.target} · ${r.subtype} · ${r.resolution_status} · ${r.witness_count} witnesses · ${r.weight_unit}`;
      }
      tooltip.textContent = text;
      tooltip.hidden = !text;
      const box = element.getBoundingClientRect();
      tooltip.style.left = `${Math.max(4, Math.min(element.clientWidth - 240, e.clientX - box.left + 12))}px`;
      tooltip.style.top = `${Math.max(4, e.clientY - box.top + 12)}px`;
      updateSelection();
      if (
        hit &&
        propsRef.current.lensEnabled &&
        performance.now() - lastLens >= 80
      ) {
        lastLens = performance.now();
        currentLens.center = hit.point.toArray() as Vec3;
        currentLens.enabled = true;
        updateEdges();
      }
    };
    const leave = () => {
      tooltip.hidden = true;
      hoverEdge = "";
      hoverNode = "";
      updateSelection();
    };
    const lost = (e: Event) => {
      e.preventDefault();
      propsRef.current.onFailure(
        "Graphics context lost. Use the list or matrix, or retry spatial rendering.",
      );
    };
    renderer.domElement.addEventListener("pointerdown", pointerDown);
    canvas.addEventListener("pointerdown", startEdit, true);
    canvas.addEventListener("pointermove", dragEdit, true);
    canvas.addEventListener("pointerup", endEdit, true);
    canvas.addEventListener("pointercancel", endEdit, true);
    canvas.addEventListener("lostpointercapture", endEdit, true);
    canvas.addEventListener("wheel", resizeEdit, {
      capture: true,
      passive: false,
    });
    window.addEventListener("keydown", cancelEdit);
    renderer.domElement.addEventListener("pointerup", pointerUp);
    renderer.domElement.addEventListener("dblclick", doubleClick);
    renderer.domElement.addEventListener("pointermove", move);
    renderer.domElement.addEventListener("pointerleave", leave);
    renderer.domElement.addEventListener("webglcontextlost", lost);
    function animate(now: number) {
      if (disposed) return;
      frameId = requestAnimationFrame(animate);
      const delta = now - lastTime;
      lastTime = now;
      if (tween) {
        const t = Math.min(1, (now - tween.start) / 320),
          e = t * t * (3 - 2 * t);
        camera.position.lerpVectors(tween.fromEye, tween.eye, e);
        controls.target.lerpVectors(tween.fromTarget, tween.target, e);
        if (t === 1) tween = undefined;
      }
      if (controls.enabled) controls.update();
      camera.updateMatrixWorld();
      drawSelection();
      if (
        new URLSearchParams(location.search).has("debug") &&
        metrics.frames % 10 === 0
      ) {
        canvas.dataset.layoutTargets = JSON.stringify(
          [...spheres.keys()].map(projected).filter(Boolean),
        );
        canvas.dataset.layoutTargetsRevision = String(sceneRevision);
      }
      ring.quaternion.copy(camera.quaternion);
      for (const mark of hoverRings) mark.quaternion.copy(camera.quaternion);
      const boxes: { x: number; y: number; w: number; h: number }[] = [];
      const ordered = [...labels.entries()].sort(
        ([a], [b]) =>
          Number(b === propsRef.current.selectedId) -
          Number(a === propsRef.current.selectedId),
      );
      for (const [id, label] of ordered) {
        const s = spheres.get(id);
        if (!s) continue;
        screen.set(...s.center);
        screen.y += s.radius * 1.1;
        screen.project(camera);
        const x = (screen.x * 0.5 + 0.5) * element.clientWidth,
          y = (-screen.y * 0.5 + 0.5) * element.clientHeight,
          w = Math.min(210, (label.textContent?.length ?? 1) * 7 + 16),
          h = 24;
        const visible =
          screen.z > -1 &&
          screen.z < 1 &&
          x > -20 &&
          x < element.clientWidth + 20 &&
          y > 0 &&
          y < element.clientHeight &&
          (id === propsRef.current.selectedId ||
            !boxes.some(
              (b) =>
                Math.abs(x - b.x) < (w + b.w) / 2 + 5 && Math.abs(y - b.y) < h,
            ));
        label.style.opacity = visible ? "1" : "0";
        label.style.transform = `translate(${x}px,${y}px) translate(-50%,-100%)`;
        if (visible) boxes.push({ x, y, w, h });
      }
      renderer.render(scene, camera);
      metrics.frames++;
      if (delta > 0) {
        metrics.fps.push(1000 / delta);
        if (metrics.fps.length > 600) metrics.fps.shift();
      }
      metrics.drawCalls = renderer.info.render.calls;
      metrics.triangles = renderer.info.render.triangles;
      metrics.geometries = renderer.info.memory.geometries;
      metrics.textures = renderer.info.memory.textures;
    }
    update();
    frameId = requestAnimationFrame(animate);
    return () => {
      disposed = true;
      cancelAnimationFrame(frameId);
      resize.disconnect();
      element.parentElement?.style.removeProperty("--layout-tools-bottom");
      controls.dispose();
      canvas.removeEventListener("pointerdown", startEdit, true);
      canvas.removeEventListener("pointermove", dragEdit, true);
      canvas.removeEventListener("pointerup", endEdit, true);
      canvas.removeEventListener("pointercancel", endEdit, true);
      canvas.removeEventListener("lostpointercapture", endEdit, true);
      canvas.removeEventListener("wheel", resizeEdit, true);
      window.removeEventListener("keydown", cancelEdit);
      marquee.remove();
      groupBox.remove();
      renderer.domElement.removeEventListener("pointerdown", pointerDown);
      renderer.domElement.removeEventListener("pointerup", pointerUp);
      renderer.domElement.removeEventListener("dblclick", doubleClick);
      renderer.domElement.removeEventListener("pointermove", move);
      renderer.domElement.removeEventListener("pointerleave", leave);
      tooltip.remove();
      renderer.domElement.removeEventListener("webglcontextlost", lost);
      for (const bucket of Object.values(buckets)) bucket.mesh.dispose();
      sphereGeometry.dispose();
      Object.values(materials).forEach((m) => m.dispose());
      lines.geometry.dispose();
      lineMaterial.dispose();
      for (const object of declaredLayer.children)
        (object as THREE.Line).geometry.dispose();
      declaredMaterial.dispose();
      selectedLine.geometry.dispose();
      selectedMaterial.dispose();
      ringGeometry.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
      labelLayer.remove();
      controller.current = undefined;
    };
  }, []);
  useEffect(
    () => controller.current?.update(),
    [
      props.frame,
      props.declaredLinks,
      props.navigationKey,
      props.selectedId,
      props.selectedEdge,
      props.highlightedEdges,
      props.violations,
      props.beta,
      props.lensEnabled,
      props.theme,
    ],
  );
  return (
    <div ref={host} className="scene-host" data-testid="spatial-scene">
      <div
        className="scene-layout-tools"
        role="group"
        aria-label="Layout tools"
      >
        <button aria-pressed={boxMode} onClick={() => setBoxMode((v) => !v)}>
          Box select
        </button>
        <span data-testid="layout-selection-status" aria-live="polite">
          {editCount} selected
        </span>
        <button
          disabled={!editCount}
          onClick={() => controller.current?.scaleSelection(1.15)}
          aria-label="Size +: enlarge selected nodes"
        >
          Size +
        </button>
        <button
          disabled={!editCount}
          onClick={() => controller.current?.scaleSelection(1 / 1.15)}
          aria-label="Size −: shrink selected nodes"
        >
          Size −
        </button>
        <button
          disabled={!editCount}
          onClick={() => controller.current?.moveSelection(-1, 0)}
          aria-label="Move selected nodes left"
        >
          ←
        </button>
        <button
          disabled={!editCount}
          onClick={() => controller.current?.moveSelection(1, 0)}
          aria-label="Move selected nodes right"
        >
          →
        </button>
        <button
          disabled={!editCount}
          onClick={() => controller.current?.moveSelection(0, 1)}
          aria-label="Move selected nodes up"
        >
          ↑
        </button>
        <button
          disabled={!editCount}
          onClick={() => controller.current?.moveSelection(0, -1)}
          aria-label="Move selected nodes down"
        >
          ↓
        </button>
        <button onClick={() => controller.current?.resetLayout()}>
          Reset layout
        </button>
      </div>
      <p
        className="scene-edit-help"
        style={{ color: props.theme === "light" ? "#4b5563" : "#b7bec7" }}
      >
        Drag background to orbit · wheel to zoom · Hold a bubble rim: drag to
        move, wheel to resize · Shift-drag / Box select: select a group. Manual
        placement leaves relationships unchanged.
      </p>
      {failure && (
        <div className="scene-failure" role="status">
          {failure}
        </div>
      )}
    </div>
  );
});
