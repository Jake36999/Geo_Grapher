/* Derive runtime JSON Schemas directly from the approved declaration contract. */
const ts = require('typescript');
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const version = process.argv[2] || '1.0';
if (!['1.0','1.1'].includes(version)) throw new Error('Unsupported contract version');
const contractRoot = version === '1.0' ? 'contracts' : 'contracts/v1.1';
const text = fs.readFileSync(path.join(root, contractRoot, 'geographer.wire.d.ts'), 'utf8');
const source = ts.createSourceFile('geographer.wire.d.ts', text, ts.ScriptTarget.Latest, true);
const declarations = new Map(source.statements.filter(n => ts.isInterfaceDeclaration(n) || ts.isTypeAliasDeclaration(n)).map(n => [n.name.text,n]));
const defs = {};
const clone = x => JSON.parse(JSON.stringify(x));
const hash = x => crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex').slice(0,12);
function ref(name, args=[]) {
  const key = args.length ? name+'_'+hash(args) : name;
  if (!defs[key]) {
    const node = declarations.get(name);
    if (!node) throw new Error('Unknown contract type '+name);
    const env = {};
    (node.typeParameters || []).forEach((p,i) => {env[p.name.text]=args[i];});
    defs[key] = {};
    defs[key] = ts.isInterfaceDeclaration(node) ? object(node, env) : type(node.type,env);
  }
  return {$ref:'#/$defs/'+key};
}
function object(node, env) {
  const result={type:'object',properties:{},required:[],additionalProperties:false};
  for (const clause of node.heritageClauses || []) for (const parent of clause.types) {
    const r=ref(parent.expression.getText(source),(parent.typeArguments||[]).map(t=>type(t,env)));
    const base=defs[r.$ref.split('/').pop()];
    Object.assign(result.properties,clone(base.properties)); result.required.push(...base.required);
  }
  for (const field of node.members) {
    if (!ts.isPropertySignature(field)) throw new Error('Unsupported interface member');
    const name=field.name.getText(source).replace(/^['"]|['"]$/g,'');
    result.properties[name]=constrain(name,type(field.type,env));
    if (!field.questionToken) result.required.push(name);
  }
  result.required=[...new Set(result.required)];
  return result;
}
function type(node,env) {
  if (!node) throw new Error('Missing type');
  if (node.kind===ts.SyntaxKind.StringKeyword) return {type:'string'};
  if (node.kind===ts.SyntaxKind.NumberKeyword) return {type:'number'};
  if (node.kind===ts.SyntaxKind.BooleanKeyword) return {type:'boolean'};
  if (ts.isLiteralTypeNode(node)) {
    const l=node.literal;
    if (l.kind===ts.SyntaxKind.NullKeyword) return {type:'null'};
    if (l.kind===ts.SyntaxKind.TrueKeyword || l.kind===ts.SyntaxKind.FalseKeyword) return {const:l.kind===ts.SyntaxKind.TrueKeyword};
    return {const:ts.isNumericLiteral(l)?Number(l.text):l.text};
  }
  if (ts.isArrayTypeNode(node)) return {type:'array',items:type(node.elementType,env)};
  if (ts.isTupleTypeNode(node)) return {type:'array',prefixItems:node.elements.map(x=>type(x,env)),minItems:node.elements.length,maxItems:node.elements.length};
  if (ts.isParenthesizedTypeNode(node)) return type(node.type,env);
  if (ts.isUnionTypeNode(node)) return {anyOf:node.types.map(x=>type(x,env))};
  if (ts.isTypeLiteralNode(node)) return object(node,env);
  if (ts.isTypeReferenceNode(node)) {
    const name=node.typeName.getText(source);
    if (name==='Record' && node.typeArguments?.length===2 && node.typeArguments[0].kind===ts.SyntaxKind.StringKeyword)
      return {type:'object',additionalProperties:type(node.typeArguments[1],env)};
    return env[name] ? clone(env[name]) : ref(name,(node.typeArguments||[]).map(x=>type(x,env)));
  }
  throw new Error('Unsupported type '+node.getText(source));
}
function constrain(name,schema) {
  const s=clone(schema);
  if (s.anyOf) {s.anyOf=s.anyOf.map(x=>constrain(name,x)); return s;}
  if (s.type==='object' && ['kind_counts','reason_counts'].includes(name))
    s.additionalProperties={type:'integer',minimum:0,maximum:Number.MAX_SAFE_INTEGER};
  const bounds={limit_tokens:[256,32768],limit:[1,200],page_size:[1,200],evidence_page_size:[1,50],
    ...(version==='1.1'?{review_limit:[1,100],max_hops:[0,64],max_expansions:[1,200000],max_anchor_subjects:[1,2000]}:{}),
    max_depth:[0,64],max_results:[1,1000],max_diameter:[0,8],node_budget:[1,500],curve_budget:[0,2000],
    width_px:[1,16384],height_px:[1,16384],start_line:[1,Number.MAX_SAFE_INTEGER],end_line:[1,Number.MAX_SAFE_INTEGER]};
  if (s.type==='number') {
    const integer=Boolean(bounds[name]) || /(_count|_tokens|_size|_depth|_rank|_diameter)$/.test(name) ||
      /^(omitted_|depth$|dag_rank$|lane_index$|lane_count$|sample_count$|n$|m$|max_degree$|parity_degree$|A$|B$)/.test(name);
    if (integer) {s.type='integer';s.minimum=0;s.maximum=Number.MAX_SAFE_INTEGER;}
    if (bounds[name]) [s.minimum,s.maximum]=bounds[name];
    if (['beta','strength','confidence','ratio'].includes(name)) {s.minimum=0;s.maximum=1;}
    if (['radius','near'].includes(name)) s.exclusiveMinimum=0;
    if (name==='device_pixel_ratio') {s.exclusiveMinimum=0;s.maximum=4;}
    if (name==='fov_y_degrees') {s.exclusiveMinimum=1;s.exclusiveMaximum=179;}
  }
  if (name==='request_id' || name==='query') return {type:'string',minLength:1,maxLength:name==='request_id'?128:4096,'x-maxUtf8Bytes':name==='request_id'?128:4096};
  if (s.type==='array' && ['repo_ids','pins','revealed_ids','families','subtypes','resolution_statuses','kinds'].includes(name)) {
    s.uniqueItems=true;
    if (['families','resolution_statuses'].includes(name) && !(version==='1.1' && name==='families')) s.minItems=1;
  }
  if (s.type==='array' && ['witness_preview','top_exemplars'].includes(name)) s.maxItems=name==='witness_preview'?3:5;
  if (s.type==='string' && ['signature','doc_gist'].includes(name)) s.maxLength=name==='signature'?240:140;
  return s;
}
const operationNode=declarations.get('OperationMap');
const operations={};
for (const property of operationNode.members) {
  const op=property.name.getText(source);
  const properties=object(property.type,{}).properties;
  operations[op]=properties;
}
defs.Id={type:'string',minLength:1,maxLength:512,'x-maxUtf8Bytes':512};
defs.Digest={type:'string',pattern:'^[0-9a-f]{64}$'};
defs.Cursor={type:'string',minLength:1,maxLength:4096,'x-maxUtf8Bytes':4096};
const output={$schema:'https://json-schema.org/draft/2020-12/schema',contract_sha256:crypto.createHash('sha256').update(text).digest('hex'),operations,$defs:defs};
const directory=path.join(root,contractRoot,'generated');fs.mkdirSync(directory,{recursive:true});
fs.writeFileSync(path.join(directory,'geographer.wire.schema.json'),JSON.stringify(output,null,2)+'\n');
console.log('Generated schemas for '+Object.keys(operations).length+' operations from the '+version+' declaration file.');
