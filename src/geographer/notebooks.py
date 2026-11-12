import ast
import hashlib
import json
from dataclasses import dataclass
from typing import Tuple

class NotebookFormatError(ValueError):
    """Raised when the input notebook is structurally invalid."""
    pass

@dataclass(frozen=True)
class CellSpan:
    index: int
    cell_type: str          # 'code' | 'markdown' | 'raw'; any other type is treated as 'raw'
    start_line: int         # 1-based line of this cell's header in python_text
    end_line: int           # 1-based last line of this cell (== start_line for an empty cell)

@dataclass(frozen=True)
class NotebookSource:
    python_text: str
    cells: Tuple[CellSpan, ...]
    notebook_sha256: str    # hashlib.sha256(raw).hexdigest()
    unparsed: Tuple[int, ...]   # indexes of code cells that failed ast.parse, ascending
    cell_texts: Tuple[str, ...] # each cell's original joined source text, in order

    def cell_text(self, index: int) -> str:
        """Return the original joined source text for the given cell index."""
        return self.cell_texts[index]


def to_virtual_source(raw: bytes, rel_path: str) -> NotebookSource:
    """Convert raw ipynb JSON bytes into a NotebookSource with a virtual Python script."""
    # Decode UTF-8 (with BOM tolerance) and load JSON
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NotebookFormatError(f"{rel_path}: not valid UTF-8") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NotebookFormatError(f"{rel_path}: invalid JSON") from exc

    # Validate top-level structure
    if not isinstance(data, dict):
        raise NotebookFormatError(f"{rel_path}: top-level value must be a dict")
    nbformat = data.get("nbformat")
    if not isinstance(nbformat, int) or nbformat < 4:
        raise NotebookFormatError(f"{rel_path}: missing or unsupported nbformat")
    cells = data.get("cells")
    if cells is None or not isinstance(cells, list):
        raise NotebookFormatError(f"{rel_path}: missing or invalid cells")

    all_lines = []          # lines of the resulting python_text
    cell_spans = []         # collected CellSpan objects
    cell_texts = []         # original joined source per cell
    unparsed = []           # indexes of unparsed code cells
    current_line = 1        # 1-based line number of the next line to write

    for idx, cell in enumerate(cells):
        # Determine cell type – treat anything other than the three known types as 'raw'
        cell_type = cell.get("cell_type", "raw")
        if cell_type not in ("code", "markdown", "raw"):
            cell_type = "raw"

        # Extract and join the cell source
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        original_text = source
        cell_texts.append(original_text)

        # Split into lines (without trailing newline characters)
        lines = original_text.splitlines()

        # Build header line and body lines depending on cell type
        if cell_type == "code":
            # Apply magic handling: comment out lines starting with % or !
            magic_lines = []
            for line in lines:
                stripped = line.lstrip()
                if stripped and stripped[0] in ("%", "!"):
                    magic_lines.append("# " + line)
                else:
                    magic_lines.append(line)
            # Test if the resulting cell body is valid Python
            try:
                ast.parse("\n".join(magic_lines), mode="exec")
            except SyntaxError:
                # Entire cell is commented out; mark header accordingly
                body = ["# " + line for line in lines]   # use original lines
                header = f"# %% [cell {idx}] code (unparsed)"
                unparsed.append(idx)
            else:
                body = magic_lines
                header = f"# %% [cell {idx}] code"
        else:
            # markdown, raw, or any other type: comment every line
            body = ["# " + line for line in lines]
            header = f"# %% [cell {idx}] {cell_type}"

        # Add lines and compute span
        start_line = current_line
        all_lines.append(header)
        if body:
            all_lines.extend(body)
            end_line = start_line + len(body)
        else:
            end_line = start_line

        cell_spans.append(CellSpan(
            index=idx,
            cell_type=cell_type,
            start_line=start_line,
            end_line=end_line,
        ))
        current_line = end_line + 1

    python_text = "\n".join(all_lines) + "\n"
    sha = hashlib.sha256(raw).hexdigest()

    return NotebookSource(
        python_text=python_text,
        cells=tuple(cell_spans),
        notebook_sha256=sha,
        unparsed=tuple(unparsed),
        cell_texts=tuple(cell_texts),
    )
