"""Validated Tiptap documents; shared semantic and inline rendering."""

import copy
import html
import json
import os
import re
from urllib.parse import quote, urlsplit
from bs4 import BeautifulSoup, NavigableString
from premailer import transform
from .content import MD, asset_path
from .render import templates, TEMPLATE_DIR

EMPTY = {"type": "doc", "content": [{"type": "paragraph"}]}
TAGS = {
    "paragraph": "p",
    "blockquote": "blockquote",
    "bulletList": "ul",
    "orderedList": "ol",
    "listItem": "li",
    "codeBlock": "pre",
    "table": "table",
    "tableRow": "tr",
    "tableCell": "td",
    "tableHeader": "th",
}
MARKS = {
    "bold": "strong",
    "italic": "em",
    "underline": "u",
    "strike": "s",
    "code": "code",
}


def css_for(template):
    if template == "none":
        return ".article {font-size:16px;line-height:1.8;} img {max-width:100%;height:auto;}"
    if template not in templates():
        raise ValueError("未知模板")
    return (TEMPLATE_DIR / f"{template}.css").read_text()


def safe_link(value):
    if (
        not isinstance(value, str)
        or len(value) > 2000
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError("链接无效")
    if urlsplit(value).scheme not in ("https", "http", "mailto"):
        raise ValueError("链接仅支持 http/https/mailto")
    return value


def styles(attrs):
    result = {}
    rules = {
        "color": r"#[0-9a-fA-F]{6}",
        "backgroundColor": r"#[0-9a-fA-F]{6}",
        "fontSize": r"(?:1[2-9]|2[0-9]|3[0-6])px",
        "textAlign": r"left|center|right",
        "align": r"left|center|right",
        "width": r"25%|50%|75%|100%",
        "borderRadius": r"0px|4px|8px|12px",
        "spacing": r"0px|8px|16px|24px",
        "quoteStyle": r"plain|accent",
    }
    names = {
        "color": "color",
        "backgroundColor": "background-color",
        "fontSize": "font-size",
        "textAlign": "text-align",
        "align": "text-align",
        "width": "width",
        "borderRadius": "border-radius",
        "spacing": "margin-bottom",
    }
    for key, pattern in rules.items():
        value = attrs.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not re.fullmatch(pattern, value):
            raise ValueError(f"样式属性无效：{key}")
        if key in names:
            result[names[key]] = value
        elif value == "plain":
            result.update({"border-left": "none", "background": "none"})
    return ";".join(f"{k}:{v}" for k, v in result.items())


def validate_doc(doc, assets):
    if not isinstance(doc, dict) or doc.get("type") != "doc":
        raise ValueError("需要 Tiptap doc")
    if len(json.dumps(doc, ensure_ascii=False).encode()) > 500_000:
        raise ValueError("正文超过500KB")
    refs = []
    count = 0
    allowed_attrs = {
        "paragraph": {"textAlign", "spacing"},
        "heading": {"level", "textAlign", "spacing"},
        "blockquote": {"quoteStyle", "spacing"},
        "image": {
            "src",
            "alt",
            "title",
            "caption",
            "width",
            "textAlign",
            "borderRadius",
        },
        "orderedList": {"start", "type"},
        "codeBlock": {"language"},
        "tableCell": {"colspan", "rowspan", "colwidth", "align"},
        "tableHeader": {"colspan", "rowspan", "colwidth", "align"},
    }
    block = {
        "paragraph",
        "heading",
        "blockquote",
        "bulletList",
        "orderedList",
        "codeBlock",
        "horizontalRule",
        "image",
        "table",
    }
    children = {
        "doc": block,
        "paragraph": {"text", "hardBreak"},
        "heading": {"text", "hardBreak"},
        "blockquote": block,
        "bulletList": {"listItem"},
        "orderedList": {"listItem"},
        "listItem": block,
        "codeBlock": {"text"},
        "table": {"tableRow"},
        "tableRow": {"tableCell", "tableHeader"},
        "tableCell": block,
        "tableHeader": block,
    }

    def visit(n, depth=0):
        nonlocal count
        count += 1
        if depth > 40 or count > 10000 or not isinstance(n, dict):
            raise ValueError("文档结构过大或无效")
        kind = n.get("type")
        attrs = n.get("attrs", {})
        if kind not in {
            *TAGS,
            "doc",
            "text",
            "heading",
            "image",
            "hardBreak",
            "horizontalRule",
        }:
            raise ValueError("不支持的节点")
        if not isinstance(attrs, dict) or set(attrs) - allowed_attrs.get(kind, set()):
            raise ValueError("不支持的节点属性")
        styles(attrs)
        if kind == "heading" and attrs.get("level") not in (1, 2, 3):
            raise ValueError("标题仅支持 H1/H2/H3")
        if kind == "text" and (not isinstance(n.get("text"), str) or not n["text"]):
            raise ValueError("文本无效")
        if kind == "image":
            name = asset_path(attrs.get("src", ""))
            if name not in assets:
                raise ValueError(f"图片不存在：{name}")
            refs.append(name)
            for key in ("alt", "title", "caption"):
                if attrs.get(key) is not None and (
                    not isinstance(attrs[key], str) or len(attrs[key]) > 1000
                ):
                    raise ValueError("图片说明过长")
        if kind in ("tableCell", "tableHeader"):
            for key in ("colspan", "rowspan"):
                if (
                    not isinstance(attrs.get(key, 1), int)
                    or not 1 <= attrs.get(key, 1) <= 20
                ):
                    raise ValueError("表格跨度无效")
            if attrs.get("colwidth") is not None and (
                not isinstance(attrs["colwidth"], list)
                or any(
                    not isinstance(x, int) or not 1 <= x <= 2000
                    for x in attrs["colwidth"]
                )
            ):
                raise ValueError("表格宽度无效")
        if kind == "orderedList" and attrs.get("type") not in (
            None,
            "1",
            "a",
            "A",
            "i",
            "I",
        ):
            raise ValueError("列表类型无效")
        if kind == "orderedList" and (
            not isinstance(attrs.get("start", 1), int)
            or not 1 <= attrs.get("start", 1) <= 10000
        ):
            raise ValueError("列表编号无效")
        if n.get("marks") and kind != "text":
            raise ValueError("marks 仅用于文本")
        for mark in n.get("marks", []):
            m = mark.get("type")
            a = mark.get("attrs", {})
            if m not in {*MARKS, "link", "textStyle", "highlight"} or not isinstance(
                a, dict
            ):
                raise ValueError("不支持的文本属性")
            allowed = {
                "link": {"href", "target", "rel", "class"},
                "textStyle": {
                    "color",
                    "backgroundColor",
                    "fontSize",
                    "fontFamily",
                    "lineHeight",
                },
                "highlight": {"color"},
            }.get(m, set())
            if set(a) - allowed:
                raise ValueError("不支持的文本属性")
            if m == "link":
                safe_link(a.get("href"))
            if m == "textStyle":
                if a.get("fontFamily") or a.get("lineHeight"):
                    raise ValueError("不支持自定义字体或行高")
                styles(a)
            if m == "highlight":
                styles({"backgroundColor": a.get("color")})
        content = n.get("content", [])
        if not isinstance(content, list):
            raise ValueError("节点内容无效")
        for child in content:
            if not isinstance(child, dict) or child.get("type") not in children.get(
                kind, set()
            ):
                raise ValueError("节点嵌套无效")
            visit(child, depth + 1)

    visit(doc)
    return list(dict.fromkeys(refs))


def render_doc(
    doc,
    template,
    assets,
    version_id=None,
    article_id=None,
    urls=None,
    template_css=None,
):
    validate_doc(doc, assets)

    def esc(value):
        return html.escape(str(value), quote=True)

    def node(n):
        kind = n["type"]
        a = n.get("attrs", {})
        body = "".join(node(c) for c in n.get("content", []))
        if kind == "text":
            text = esc(n["text"])
            for m in n.get("marks", []):
                typ = m["type"]
                ma = m.get("attrs", {})
                if typ in MARKS:
                    text = f"<{MARKS[typ]}>{text}</{MARKS[typ]}>"
                elif typ == "link":
                    text = f'<a href="{esc(safe_link(ma["href"]))}">{text}</a>'
                else:
                    style = (
                        styles({"backgroundColor": ma.get("color")})
                        if typ == "highlight"
                        else styles(ma)
                    )
                    if style:
                        text = f'<span style="{esc(style)}">{text}</span>'
            return text
        if kind == "doc":
            return body
        if kind == "hardBreak":
            return "<br>"
        if kind == "horizontalRule":
            return "<hr>"
        if kind == "image":
            name = a["src"]
            prefix = os.getenv("PUBLISHER_BASE_PATH", "").rstrip("/")
            src = (
                urls[name]
                if urls is not None
                else (
                    f"{prefix}/api/v1/versions/{version_id}/assets/{quote(name)}"
                    if version_id
                    else f"{prefix}/api/v2/articles/{article_id}/assets/{quote(name)}"
                )
            )
            style = styles(a) + ";height:auto;max-width:100%;display:block"
            align = a.get("textAlign")
            if align:
                style += (
                    ";margin-left:"
                    + ("0" if align == "left" else "auto")
                    + ";margin-right:"
                    + ("0" if align == "right" else "auto")
                )
            img = f'<img src="{esc(src)}" alt="{esc(a.get("alt") or "")}" style="{esc(style)}">'
            return (
                f"<figure>{img}<figcaption>{esc(a['caption'])}</figcaption></figure>"
                if a.get("caption")
                else img
            )
        tag = f"h{a['level']}" if kind == "heading" else TAGS[kind]
        attr = f' style="{esc(styles(a))}"' if styles(a) else ""
        if kind == "orderedList":
            attr += f' start="{a.get("start", 1)}"'
            if a.get("type"):
                attr += f' type="{esc(a["type"])}"'
        if kind in ("tableCell", "tableHeader"):
            attr += f' colspan="{a.get("colspan", 1)}" rowspan="{a.get("rowspan", 1)}"'
        if kind == "codeBlock":
            body = f"<code>{body}</code>"
        return f"<{tag}{attr}>{body}</{tag}>"

    rendered = transform(
        '<section class="article">' + node(doc) + "</section>",
        css_text=template_css if template_css is not None else css_for(template),
        allow_network=False,
        allow_loading_external_files=False,
        remove_classes=True,
        disable_leftover_css=True,
    )
    soup = BeautifulSoup(rendered, "html.parser")
    return "".join(str(x) for x in soup.body.contents)


def from_markdown(markdown, mapping=None):
    soup = BeautifulSoup(MD.render(markdown), "html.parser")
    mapping = mapping or {}
    inverse = {v: k for k, v in TAGS.items()}

    def inline(el, marks=None):
        marks = marks or []
        if isinstance(el, NavigableString):
            return (
                [
                    {
                        "type": "text",
                        "text": str(el),
                        **({"marks": marks} if marks else {}),
                    }
                ]
                if str(el)
                else []
            )
        if el.name == "br":
            return [{"type": "hardBreak"}]
        if el.name == "img":
            return [
                {
                    "type": "image",
                    "attrs": {
                        "src": mapping.get(
                            asset_path(el["src"]), asset_path(el["src"])
                        ),
                        "alt": el.get("alt", ""),
                    },
                }
            ]
        mark = next((k for k, v in MARKS.items() if v == el.name), None)
        if el.name == "a":
            try:
                safe_link(el.get("href"))
                extra = [{"type": "link", "attrs": {"href": el["href"]}}]
            except ValueError:
                extra = []
        else:
            extra = [{"type": mark}] if mark else []
        return [n for child in el.children for n in inline(child, marks + extra)]

    def block(el):
        if isinstance(el, NavigableString):
            return []
        if el.name == "hr":
            return [{"type": "horizontalRule"}]
        if el.name in ("thead", "tbody"):
            return [n for ch in el.children for n in block(ch)]
        typ = "heading" if re.fullmatch("h[1-6]", el.name) else inverse.get(el.name)
        if not typ:
            return []
        attrs = {"level": min(int(el.name[1]), 3)} if typ == "heading" else {}
        if typ == "orderedList":
            attrs["start"] = int(el.get("start", 1))
        if typ == "codeBlock":
            return [
                {
                    "type": "codeBlock",
                    **({"content": [{"type": "text", "text": el.get_text()}]} if el.get_text() else {}),
                }
            ]
        if typ in ("listItem", "tableCell", "tableHeader"):
            content = []
            pending = []

            def flush_inline():
                if pending:
                    content.append({"type": "paragraph", "content": pending.copy()})
                    pending.clear()

            for child in el.children:
                if not isinstance(child, NavigableString) and (
                    child.name in inverse
                    or child.name in ("hr", "thead", "tbody")
                    or re.fullmatch("h[1-6]", child.name)
                ):
                    flush_inline()
                    content.extend(block(child))
                elif (
                    not isinstance(child, NavigableString)
                    or str(child).strip()
                    or pending
                ):
                    for n in inline(child):
                        if n["type"] == "image":
                            flush_inline()
                            content.append(n)
                        else:
                            pending.append(n)
            flush_inline()
            if not content or (typ == "listItem" and content[0]["type"] != "paragraph"):
                content.insert(0, {"type": "paragraph"})
            if typ in ("tableCell", "tableHeader"):
                match = re.search(
                    r"text-align:\s*(left|center|right)", el.get("style", "")
                )
                if match:
                    attrs["align"] = match[1]
        else:
            content = [
                n
                for ch in el.children
                for n in (inline(ch) if typ in ("paragraph", "heading") else block(ch))
            ]
        # Images are block nodes in Tiptap; split paragraphs around them.
        if typ == "paragraph" and any(n["type"] == "image" for n in content):
            out = []
            pending = []
            for n in content:
                if n["type"] == "image":
                    if pending:
                        out.append({"type": "paragraph", "content": pending})
                        pending = []
                    out.append(n)
                else:
                    pending.append(n)
            if pending:
                out.append({"type": "paragraph", "content": pending})
            return out
        return [
            {
                "type": typ,
                **({"attrs": attrs} if attrs else {}),
                **({"content": content} if content else {}),
            }
        ]

    return {
        "type": "doc",
        "content": [n for el in soup.children for n in block(el)]
        or copy.deepcopy(EMPTY["content"]),
    }
