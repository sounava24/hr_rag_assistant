import re
from pathlib import Path

def parse_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]

def table_to_chunks(lines, doc_name, section):
    header = parse_row(lines[0])
    out = []
    for line in lines[2:]:                      
        cells = parse_row(line)
        if len(cells) != len(header):
            continue
        text = "; ".join(f"{h}: {v}" for h, v in zip(header, cells))
        out.append({"doc_name": doc_name, "section": section,
                    "type": "table_row", "text": text})
    return out

def split_body(lines, doc_name, section):
    chunks, prose, table = [], [], []

    def flush_prose():
        t = "\n".join(prose).strip()
        if t:
            chunks.append({"doc_name": doc_name, "section": section,
                           "type": "text", "text": t})
        prose.clear()

    def flush_table():
        if len(table) >= 3:
            chunks.extend(table_to_chunks(table, doc_name, section))
        table.clear()

    for line in lines:
        if line.strip().startswith("|"):
            flush_prose()
            table.append(line)
        else:
            flush_table()
            prose.append(line)
    flush_prose()
    flush_table()
    return chunks

def chunk_markdown(text, doc_name):
    chunks, path, buf = [], [], []

    def flush():
        section = " > ".join(path) if path else "(intro)"
        chunks.extend(split_body(buf, doc_name, section))
        buf.clear()

    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush()
            level = len(m.group(1))
            path[:] = path[:level - 1] + [m.group(2).strip()]
        else:
            buf.append(line)
    flush()
    return chunks

if __name__ == "__main__":
    for f in Path("policies").glob("*.md"):
        for c in chunk_markdown(f.read_text(encoding="utf-8"), f.name):
            print(f'{c["doc_name"]} | {c["section"]} | {c["type"]} | {c["text"][:70]!r}')