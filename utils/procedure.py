import re


def _escape_markdown(text):
    """Escape Telegram Markdown special characters in plain text values."""
    text = str(text)
    for ch in ('\\', '_', '*', '`', '[', ']', '(', ')'):
        text = text.replace(ch, f'\\{ch}')
    return text


def _parse_markdown_document(content):
    """
    Parse a markdown document into sections.

    Level 1 headings (#) become top-level sections.
    Level 2 headings (##) become subsections under the most recent section.
    """
    sections = []
    current_section = None
    current_subsection = None
    heading_re = re.compile(r"^(#{1,6})\s+(.*)$")

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        match = heading_re.match(line.strip())

        if match:
            level = len(match.group(1))
            title = match.group(2).strip()

            if level == 1:
                current_section = {
                    "title": title,
                    "intro": [],
                    "subsections": [],
                }
                sections.append(current_section)
                current_subsection = None
                continue

            if level == 2 and current_section is not None:
                current_subsection = {
                    "title": title,
                    "body": [],
                }
                current_section["subsections"].append(current_subsection)
                continue

        if current_section is None:
            continue

        if current_subsection is not None:
            current_subsection["body"].append(line)
        else:
            current_section["intro"].append(line)

    return sections


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


def _render_section(section, index, subsection_index=None):
    lines = [f"📄 **Mục {index}**: {_escape_markdown(section['title'])}"]

    if subsection_index is None:
        intro_lines = [line for line in section["intro"] if line.strip()]
        if intro_lines:
            lines.append("")
            lines.append("**Nội dung chính:**")
            for line in intro_lines:
                lines.append(f"- {_escape_markdown(_normalize_bullet_line(line))}")

        if section["subsections"]:
            lines.append("")
            lines.append("**Mục con:**")
            for i, sub in enumerate(section["subsections"], 1):
                lines.append(f"{i}. {_escape_markdown(sub['title'])}")
        return "\n".join(lines)

    if subsection_index < 1 or subsection_index > len(section["subsections"]):
        return None

    subsection = section["subsections"][subsection_index - 1]
    lines.append(f"**Mục con {subsection_index}**: {_escape_markdown(subsection['title'])}")
    body_lines = [line for line in subsection["body"] if line.strip()]
    if body_lines:
        lines.append("")
        for line in body_lines:
            lines.append(f"- {_escape_markdown(_normalize_bullet_line(line))}")
    return "\n".join(lines)


def get_procedure_info(md_content):
    sections = _parse_markdown_document(md_content)
    if not sections:
        return "❌ Không tìm thấy mục `#` nào trong file Markdown."

    lines = [f"Đã nhận file quy trình Markdown.", f"Số mục chính: {len(sections)}", "", "Các mục chính:"]
    for i, section in enumerate(sections, 1):
        lines.append(f"{i}. {_escape_markdown(section['title'])}")
    lines.append("")
    lines.append("Dùng `mdquytrinh hien`, `mdquytrinh tim ~...`, `mdquytrinh xem 1`, `mdquytrinh xem 3 1`, hoặc `mdquytrinh them <file.md>`.")
    return "\n".join(lines)


def process_procedure_markdown(md_content, formula):
    """
    Process commands for a structured Markdown workflow document.
    """
    sections = _parse_markdown_document(md_content)
    formula = formula.strip()
    formula_lower = formula.lower()

    if not sections:
        return "❌ Không tìm thấy mục `#` nào trong file Markdown.", None

    if formula_lower == "hien":
        lines = ["📋 **Danh sách quy trình**:"]
        for i, section in enumerate(sections, 1):
            lines.append(f"{i}. {_escape_markdown(section['title'])}")
        lines.append("")
        lines.append("Dùng `mdquytrinh tim ~...` để tìm quy trình, `mdquytrinh xem 1` hoặc `mdquytrinh xem 3 1` để xem chi tiết, `mdquytrinh them <file.md>` để gộp thêm file.")
        return "\n".join(lines), None

    if formula_lower.startswith("tim "):
        query = formula[4:].strip()
        if query.startswith("~"):
            query = query[1:].strip()
        query = _strip_quotes(query).casefold()

        results = []
        for i, section in enumerate(sections, 1):
            haystack = " ".join(
                [
                    section["title"],
                    " ".join(section["intro"]),
                    " ".join(sub["title"] for sub in section["subsections"]),
                    " ".join(" ".join(sub["body"]) for sub in section["subsections"]),
                ]
            ).casefold()
            if query and query in haystack:
                results.append(f"{i}. {_escape_markdown(section['title'])}")

        if not results:
            return "❌ Không tìm thấy quy trình nào khớp.", None

        return "🔍 **Kết quả tìm kiếm**:\n\n" + "\n".join(results), None

    if formula_lower.startswith("xem "):
        parts = formula.split()
        if len(parts) not in (2, 3):
            return "❌ Dùng đúng dạng `xem 1` hoặc `xem 3 1`.", None

        if not parts[1].isdigit():
            return "❌ Dùng đúng dạng `xem 1` hoặc `xem 3 1`.", None

        section_index = int(parts[1])
        if section_index < 1 or section_index > len(sections):
            return "❌ Số quy trình không hợp lệ.", None

        subsection_index = None
        if len(parts) == 3:
            if not parts[2].isdigit():
                return "❌ Dùng đúng dạng `xem 1` hoặc `xem 3 1`.", None
            subsection_index = int(parts[2])

        rendered = _render_section(sections[section_index - 1], section_index, subsection_index)
        if not rendered:
            return "❌ Số mục con không hợp lệ.", None
        return rendered, None

    return "❌ Lệnh không hợp lệ cho file Markdown. Dùng `mdquytrinh hien`, `mdquytrinh tim ~...`, `mdquytrinh xem 1`, `mdquytrinh xem 3 1`, hoặc `mdquytrinh them <file.md>`.", None
