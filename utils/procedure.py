import html
import re


def _escape_html(text):
    """Escape HTML special characters for Telegram HTML parse mode."""
    return html.escape(str(text), quote=False)


def _parse_markdown_document(content):
    """
    Parse a markdown document into a heading tree.

    The parser keeps the full hierarchy of headings so callers can navigate
    documents with up to 6 levels. For the current bot flow we mainly use
    `#`, `##`, and `###`.
    """
    sections = []
    stack = []
    heading_re = re.compile(r"^(#{1,6})\s+(.*)$")

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        match = heading_re.match(line.strip())

        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            node = {
                "title": title,
                "level": level,
                "body": [],
                "children": [],
            }

            while stack and stack[-1]["level"] >= level:
                stack.pop()

            if stack:
                stack[-1]["children"].append(node)
            else:
                sections.append(node)

            stack.append(node)
            continue

        if not stack:
            continue

        stack[-1]["body"].append(line)

    return sections


def _serialize_markdown_document(nodes):
    """Render the parsed heading tree back to markdown text."""
    lines = []

    def walk(node_list):
        for node in node_list:
            lines.append(f"{'#' * node['level']} {node['title']}")
            for line in node["body"]:
                lines.append(line)
            if node["children"]:
                walk(node["children"])

    walk(nodes)
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def count_procedure_sections(md_content):
    """Return the number of top-level `#` sections in a markdown document."""
    return len(_parse_markdown_document(md_content))


def merge_procedure_documents(base_content, extra_content):
    """
    Merge two markdown procedure documents by appending the extra document.

    Both documents keep their original `#` / `##` structure; the second file's
    top-level sections will become the next numbered sections after upload.
    """
    base = (base_content or "").rstrip()
    extra = (extra_content or "").lstrip()
    if not base:
        return extra
    if not extra:
        return base
    return base + "\n\n" + extra


def _strip_quotes(text):
    if (text.startswith("'") and text.endswith("'")) or (text.startswith('"') and text.endswith('"')):
        return text[1:-1]
    return text


def _normalize_bullet_line(line):
    """Remove an existing markdown bullet marker so we can render consistently."""
    return re.sub(r"^\s*[-*]\s*", "", str(line)).strip()


def _format_path(path):
    return " ".join(str(part) for part in path)


def _get_node_by_path(nodes, path):
    current_nodes = nodes
    node = None
    for index in path:
        if index < 1 or index > len(current_nodes):
            return None
        node = current_nodes[index - 1]
        current_nodes = node["children"]
    return node


def _delete_node_by_path(nodes, path):
    if not path:
        return None

    current_nodes = nodes
    for index in path[:-1]:
        if index < 1 or index > len(current_nodes):
            return None
        current_nodes = current_nodes[index - 1]["children"]

    target_index = path[-1] - 1
    if target_index < 0 or target_index >= len(current_nodes):
        return None

    return current_nodes.pop(target_index)


def _collect_text(node):
    parts = [node["title"], " ".join(node["body"])]
    return " ".join(part for part in parts if part).strip()


def _render_node(node, path, recursive=False, depth=0):
    indent = "  " * depth
    lines = [f"{indent}📄 <b>{_escape_html(node['title'])}</b>"]
    if depth == 0:
        lines.insert(0, f"🔎 <b>Vị trí:</b> {_escape_html(_format_path(path))}")

    body_lines = [line for line in node["body"] if line.strip()]
    if body_lines:
        lines.append("")
        lines.append(f"{indent}<b>Nội dung:</b>")
        for line in body_lines:
            lines.append(f"{indent}• {_escape_html(_normalize_bullet_line(line))}")

    if node["children"]:
        lines.append("")
        if recursive:
            lines.append(f"{indent}<b>Chi tiết bên dưới:</b>")
            for i, child in enumerate(node["children"], 1):
                child_path = path + [i]
                lines.append(_render_node(child, child_path, recursive=True, depth=depth + 1))
        else:
            lines.append(f"{indent}<b>Mục con:</b>")
            for i, child in enumerate(node["children"], 1):
                lines.append(f"{indent}{i}. {_escape_html(child['title'])}")
    return "\n".join(lines)


def get_procedure_info(md_content):
    sections = _parse_markdown_document(md_content)
    if not sections:
        return "❌ Không tìm thấy mục # nào trong file Markdown."

    lines = [f"Đã nhận file quy trình Markdown.", f"Số mục chính: {len(sections)}", "", "Các mục chính:"]
    for i, section in enumerate(sections, 1):
        lines.append(f"{i}. {_escape_html(section['title'])}")
    lines.append("")
    lines.append(
        "Dùng <b>tên_file hien</b>, <b>tên_file hien 1</b>, <b>tên_file tim ~...</b>, "
        "<b>tên_file xem 1 1</b>, <b>tên_file xem 1 1 1</b>, <b>tên_file xoa 2</b>, hoặc <b>tên_file them &lt;file.md&gt;</b>."
    )
    return "\n".join(lines)


def delete_procedure_section(md_content, path):
    """
    Delete a section identified by a 1-based heading path.

    Returns (updated_content, deleted_title) on success or (None, None) if
    the path is invalid.
    """
    sections = _parse_markdown_document(md_content)
    deleted = _delete_node_by_path(sections, path)
    if deleted is None:
        return None, None
    return _serialize_markdown_document(sections), deleted["title"]


def process_procedure_markdown(md_content, formula):
    """
    Process commands for a structured Markdown workflow document.
    """
    sections = _parse_markdown_document(md_content)
    formula = formula.strip()
    formula_lower = formula.lower()

    if not sections:
        return "❌ Không tìm thấy mục # nào trong file Markdown.", None

    parts = formula.split()
    command = parts[0].lower() if parts else ""

    def _parse_path(tokens):
        path = []
        for token in tokens:
            if not token.isdigit():
                return None
            path.append(int(token))
        return path

    if command in {"hien", "mucluc"}:
        path = _parse_path(parts[1:])
        if path is None:
            return "❌ Dùng đúng dạng <b>hien</b>, <b>hien 1</b> hoặc <b>hien 1 1</b>.", None

        if not path:
            lines = ["📋 <b>Mục lục</b>:"]
            for i, section in enumerate(sections, 1):
                lines.append(f"{i}. {_escape_html(section['title'])}")
            lines.append("")
            lines.append(
                "Dùng <b>hien 1</b> để xem chương/mục con, <b>xem 1 1</b> để xem nội dung của mục đó, "
                "<b>xem 1 1 1</b> để xem chi tiết cấp sâu hơn."
            )
            return "\n".join(lines), None

        node = _get_node_by_path(sections, path)
        if node is None:
            return "❌ Số mục không hợp lệ.", None

        if not node["children"]:
            return f"📋 <b>Mục lục {_escape_html(_format_path(path))}</b>:\n\nKhông có mục con.", None

        lines = [f"📋 <b>Mục lục {_escape_html(_format_path(path))}</b>: {_escape_html(node['title'])}"]
        for i, child in enumerate(node["children"], 1):
            child_path = path + [i]
            lines.append(f"{i}. {_escape_html(child['title'])}")
        lines.append("")
        lines.append("Dùng <b>xem</b> với cùng số thứ tự để xem nội dung chi tiết.")
        return "\n".join(lines), None

    if formula_lower.startswith("tim "):
        query = formula[4:].strip()
        if query.startswith("~"):
            query = query[1:].strip()
        query = _strip_quotes(query).casefold()

        results = []
        def walk(nodes, prefix=None):
            prefix = prefix or []
            for i, node in enumerate(nodes, 1):
                path = prefix + [i]
                haystack = _collect_text(node).casefold()
                if query and query in haystack:
                    results.append(f"{_escape_html(_format_path(path))}. {_escape_html(node['title'])}")
                walk(node["children"], path)

        walk(sections)

        if not results:
            return "❌ Không tìm thấy mục nào khớp.", None

        return "🔍 <b>Kết quả tìm kiếm</b>:\n\n" + "\n".join(results), None

    if formula_lower.startswith("xem "):
        path = _parse_path(parts[1:])
        if path is None or not (1 <= len(path) <= 3):
            return "❌ Dùng đúng dạng <b>xem 1</b>, <b>xem 1 1</b> hoặc <b>xem 1 1 1</b>.", None

        node = _get_node_by_path(sections, path)
        if node is None:
            return "❌ Số mục không hợp lệ.", None

        rendered = _render_node(node, path, recursive=True)
        return rendered, None

    return (
        "❌ Lệnh không hợp lệ cho file Markdown. Dùng <b>hien</b>, <b>hien 1</b>, <b>tim ~...</b>, "
        "<b>xem 1</b>, <b>xem 1 1</b>, <b>xem 1 1 1</b>, <b>xoa 2</b>, hoặc <b>them &lt;file.md&gt;</b>.",
        None,
    )
