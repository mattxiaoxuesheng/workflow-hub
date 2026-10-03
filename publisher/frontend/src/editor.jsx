import React, { useState, useEffect, useRef } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import { TextStyleKit } from "@tiptap/extension-text-style";
import TextAlign from "@tiptap/extension-text-align";
import Highlight from "@tiptap/extension-highlight";
import { TableKit } from "@tiptap/extension-table";
import { Extension, mergeAttributes } from "@tiptap/core";
const statuses = {
  prepared: "待确认发送",
  preparing: "正在准备",
  prepare_failed: "准备失败，可重试",
  drafting: "正在发送",
  draft: "微信草稿",
  draft_unknown: "发送结果待核对",
  submitting: "正在提交",
  publishing: "发布处理中",
  published: "已发布",
  publish_unknown: "发布结果待核对",
  publish_failed: "发布失败",
};
export const labels = {
  none: "不使用模板",
  clean: "简洁阅读",
  business: "商务报告",
  tech: "科技杂志",
};
const base = import.meta.env.BASE_URL + "api/v2";
const stamp = (d) =>
  JSON.stringify([d.title, d.template, d.content_json, d.cover]);
const frame = (s) =>
  '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0}*{box-sizing:border-box}</style></head><body>' +
  s +
  "</body></html>";
const BlockStyle = Extension.create({
  name: "blockStyle",
  addGlobalAttributes() {
    return [
      {
        types: ["paragraph", "heading", "blockquote"],
        attributes: {
          spacing: {
            default: null,
            renderHTML: (a) =>
              a.spacing ? { style: `margin-bottom:${a.spacing}` } : {},
          },
        },
      },
      {
        types: ["blockquote"],
        attributes: {
          quoteStyle: {
            default: null,
            renderHTML: (a) =>
              a.quoteStyle === "plain"
                ? { style: "border-left:none;background:none" }
                : {},
          },
        },
      },
    ];
  },
});
const ArticleImage = Image.extend({
  addOptions() {
    return { ...this.parent?.(), articleId: null };
  },
  addAttributes() {
    const { height, ...attributes } = this.parent?.() || {};
    return {
      ...attributes,
      caption: { default: null },
      width: { default: null },
      textAlign: { default: null },
      borderRadius: { default: null },
    };
  },
  renderHTML({ node, HTMLAttributes }) {
    const a = node.attrs,
      attrs = mergeAttributes(this.options.HTMLAttributes, HTMLAttributes);
    for (const k of ["caption", "width", "textAlign", "borderRadius"])
      delete attrs[k];
    attrs.src = `${base}/articles/${this.options.articleId}/assets/${a.src.split("/").map(encodeURIComponent).join("/")}`;
    attrs.style = `max-width:100%;height:auto;display:block;${a.width ? `width:${a.width};` : ""}${a.borderRadius ? `border-radius:${a.borderRadius};` : ""}${a.textAlign ? `margin-left:${a.textAlign === "left" ? "0" : "auto"};margin-right:${a.textAlign === "right" ? "0" : "auto"};` : ""}`;
    return [
      "figure",
      { "data-image": "true" },
      ["img", attrs],
      ...(a.caption ? [["figcaption", {}, a.caption]] : []),
    ];
  },
});
export default function Workspace({ api, user, exitRef }) {
  const [items, setItems] = useState([]),
    [aid, setAid] = useState(null),
    [themes, setThemes] = useState([]),
    [draft, setDraft] = useState(null),
    [version, setVersion] = useState(null),
    [tab, setTab] = useState("edit"),
    [assets, setAssets] = useState([]),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [saving, setSaving] = useState(false),
    [saved, setSaved] = useState(""),
    [preview, setPreview] = useState(null),
    [view, setView] = useState("returned"),
    [diff, setDiff] = useState(""),
    [creating, setCreating] = useState(false),
    [navigating, setNavigating] = useState(false),
    [, tick] = useState(0);
  const live = useRef(null),
    ack = useRef(""),
    queue = useRef(Promise.resolve()),
    conflict = useRef(false),
    input = useRef(null),
    job = useRef(null);
  live.current = draft;
  const dirty = !!draft && stamp(draft) !== saved;
  async function refresh() {
    setItems(await api("/articles"));
  }
  async function material(id = aid) {
    setAssets(await api(`/articles/${id}/assets`, {}, 2));
  }
  function run(fn) {
    setError("");
    setNotice("");
    setBusy(true);
    return Promise.resolve()
      .then(fn)
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  }
  function enqueue(fn) {
    const op = queue.current.catch(() => {}).then(fn);
    queue.current = op;
    return op;
  }
  async function persist() {
    const d = live.current;
    if (!d || stamp(d) === ack.current) return;
    if (conflict.current)
      throw Error("保存冲突：请下载本地修改后重新读取工作稿");
    const snapshot = { ...d };
    setSaving(true);
    try {
      const r = await api(
        `/articles/${d.article_id}/draft`,
        { method: "PUT", body: snapshot },
        2,
      );
      ack.current = stamp(snapshot);
      setSaved(ack.current);
      if (live.current?.article_id === d.article_id)
        live.current = {
          ...live.current,
          revision: r.revision,
          updated_at: r.updated_at,
        };
      setDraft((cur) =>
        cur?.article_id === d.article_id
          ? { ...cur, revision: r.revision, updated_at: r.updated_at }
          : cur,
      );
    } catch (e) {
      if (e.status === 409) conflict.current = true;
      setError("未保存：" + e.message);
      throw e;
    } finally {
      setSaving(false);
    }
  }
  function flush() {
    return enqueue(persist);
  }
  useEffect(() => {
    exitRef.current = flush;
    return () => {
      exitRef.current = null;
    };
  }, []);
  useEffect(() => {
    run(async () => {
      await refresh();
      setThemes(await api("/templates", {}, 2));
    });
  }, []);
  useEffect(() => {
    if (!dirty || conflict.current) return;
    const t = setTimeout(() => flush().catch(() => {}), 2000);
    return () => clearTimeout(t);
  }, [draft, saved]);
  useEffect(() => {
    const warn = (e) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    const hide = () => {
      if (document.visibilityState === "hidden") flush().catch(() => {});
    };
    window.addEventListener("beforeunload", warn);
    document.addEventListener("visibilitychange", hide);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("visibilitychange", hide);
    };
  }, [dirty]);
  const editor = useEditor(
    {
      extensions: [
        StarterKit.configure({
          heading: { levels: [1, 2, 3] },
          link: { openOnClick: false, protocols: ["http", "https", "mailto"] },
        }),
        ArticleImage.configure({ articleId: aid }),
        TextStyleKit.configure({ fontFamily: false, lineHeight: false }),
        TextAlign.configure({
          types: ["heading", "paragraph"],
          defaultAlignment: null,
        }),
        Highlight.configure({ multicolor: true }),
        BlockStyle,
        TableKit,
      ],
      content: { type: "doc", content: [{ type: "paragraph" }] },
      editorProps: {
        attributes: { class: "article" },
        handlePaste: (_v, e) => {
          const f = Array.from(e.clipboardData?.files || []).find((f) =>
            f.type.startsWith("image/"),
          );
          if (f) {
            e.preventDefault();
            run(() => upload(f));
            return true;
          }
          return false;
        },
        handleDrop: (_v, e) => {
          const f = Array.from(e.dataTransfer?.files || []).find((f) =>
            f.type.startsWith("image/"),
          );
          if (f) {
            e.preventDefault();
            run(() => upload(f));
            return true;
          }
          return false;
        },
      },
      onUpdate: ({ editor }) =>
        setDraft((d) => (d ? { ...d, content_json: editor.getJSON() } : d)),
      onSelectionUpdate: () => tick((n) => n + 1),
      onTransaction: () => tick((n) => n + 1),
    },
    [aid],
  );
  useEffect(() => {
    editor?.setEditable(!navigating);
  }, [editor, navigating]);
  async function open(id) {
    setNavigating(true);
    editor?.setEditable(false);
    try {
      await enqueue(async () => {
        await persist();
        const d = await api(`/articles/${id}/draft`, {}, 2);
        conflict.current = false;
        ack.current = stamp(d);
        setSaved(ack.current);
        live.current = d;
        setDraft(d);
        setAid(id);
        if (
          editor?.options.extensions.find((x) => x.name === "image")?.options
            .articleId === id
        )
          editor.commands.setContent(d.content_json, { emitUpdate: false });
        setVersion(null);
        setPreview(null);
        setTab("edit");
        await material(id);
        await refresh();
      });
    } finally {
      setNavigating(false);
      if (!editor?.isDestroyed) editor?.setEditable(true);
    }
  }
  useEffect(() => {
    if (
      editor &&
      draft &&
      editor.options.extensions.find((x) => x.name === "image")?.options
        .articleId === draft.article_id
    )
      editor.commands.setContent(draft.content_json, { emitUpdate: false });
  }, [editor, draft?.article_id]);
  function snapshot() {
    return enqueue(async () => {
      await persist();
      const r = await api(
        `/articles/${aid}/versions`,
        { method: "POST", body: { revision: live.current.revision } },
        2,
      );
      // Only accept the revision returned by this transaction, never a later remote draft revision.
      const current = live.current;
      const merged = {
        ...current,
        base_version_id: r.version_id,
        revision: r.revision,
        updated_at: r.updated_at,
      };
      setDraft(merged);
      live.current = merged;
      await refresh();
      setNotice(`已保存为 V${r.number}`);
      return r.version_id;
    });
  }
  async function upload(file) {
    if (!live.current) return;
    if (file.size > 10 * 1024 ** 2) throw Error("图片最大10MB");
    const id = live.current.article_id,
      pos = editor.state.selection.from,
      j = job.current;
    job.current = null;
    const fd = new FormData();
    fd.append("file", file);
    const a = await api(
      `/articles/${id}/assets`,
      { method: "POST", body: fd },
      2,
    );
    if (live.current?.article_id !== id) return;
    if (j?.replace) {
      const node = editor.state.doc.nodeAt(j.pos);
      if (!node || node.type.name !== "image")
        throw Error("图片位置已变化，请重新选择");
      editor.commands.command(({ tr }) => {
        tr.setNodeMarkup(j.pos, undefined, { ...node.attrs, src: a.path });
        return true;
      });
    } else
      editor
        .chain()
        .focus()
        .insertContentAt(pos, {
          type: "image",
          attrs: { src: a.path, alt: file.name },
        })
        .run();
    if (!live.current.cover) setDraft((d) => ({ ...d, cover: a.path }));
    await material();
  }
  async function prepare() {
    const vid = version && tab !== "edit" ? version.id : await snapshot();
    const p = await api(`/versions/${vid}/prepare`, { method: "POST" }, 2);
    setVersion(await api("/versions/" + vid));
    setPreview({ ...p, vid });
    setTab("preview");
  }
  async function pickVersion(id) {
    const v = await api("/versions/" + id);
    setVersion(v);
    setDiff(
      v.publication ? (await api(`/versions/${id}/diff`, {}, 2)).diff : "",
    );
  }
  async function action(path) {
    await api(`/versions/${version.id}${path}`, { method: "POST" });
    await pickVersion(version.id);
    setTab("wechat");
  }
  const image = editor?.isActive("image"),
    block = image
      ? "image"
      : editor?.isActive("heading")
        ? "heading"
        : editor?.isActive("blockquote")
          ? "blockquote"
          : "paragraph",
    a = editor?.getAttributes(block) || {},
    text = editor?.getAttributes("textStyle") || {};
  const overridden = !!(
    text.color ||
    text.fontSize ||
    editor?.isActive("highlight") ||
    a.textAlign ||
    a.spacing ||
    a.width ||
    a.borderRadius ||
    a.quoteStyle ||
    editor?.isActive("bold") ||
    editor?.isActive("italic") ||
    editor?.isActive("underline")
  );
  const attr = (k, v) =>
    editor
      .chain()
      .focus()
      .updateAttributes(block, { [k]: v || null })
      .run();
  const reset = () =>
    editor
      .chain()
      .focus()
      .unsetMark("textStyle")
      .unsetHighlight()
      .unsetBold()
      .unsetItalic()
      .unsetUnderline()
      .updateAttributes(
        block,
        image
          ? { width: null, textAlign: null, borderRadius: null }
          : {
              textAlign: null,
              spacing: null,
              ...(block === "blockquote" ? { quoteStyle: null } : {}),
            },
      )
      .run();
  const article = items.find((x) => x.id === aid);
  const choose = (label, value, values, change) => (
    <label>
      {label}
      <select value={value || ""} onChange={(e) => change(e.target.value)}>
        <option value="">跟随模板</option>
        {values.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
  return (
    <>
      {error && (
        <div className="error" role="alert">
          {error}
          {conflict.current && (
            <>
              <button
                onClick={() => {
                  const b = new Blob([JSON.stringify(live.current, null, 2)], {
                      type: "application/json",
                    }),
                    u = URL.createObjectURL(b),
                    el = document.createElement("a");
                  el.href = u;
                  el.download = "unsaved-draft.json";
                  el.click();
                  URL.revokeObjectURL(u);
                }}
              >
                下载本地修改
              </button>
              <button
                onClick={() => {
                  if (
                    window.confirm("已保留本地修改，重新读取服务器工作稿？")
                  ) {
                    ack.current = stamp(live.current);
                    run(() => open(aid));
                  }
                }}
              >
                重新读取
              </button>
            </>
          )}
        </div>
      )}
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <section className="articlebar">
        <button disabled={busy} onClick={() => setCreating(true)}>
          ＋ 新建文章
        </button>
        <label className="import-button">
          ↑ 导入 Markdown / ZIP
          <input
            type="file"
            accept=".md,.markdown,.zip"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files[0];
              if (!f) return;
              run(async () => {
                await flush();
                let r;
                if (f.name.endsWith(".zip")) {
                  const fd = new FormData();
                  fd.append("file", f);
                  r = await api(
                    "/import/package",
                    { method: "POST", body: fd },
                    2,
                  );
                } else
                  r = await api(
                    "/import/markdown",
                    {
                      method: "POST",
                      body: {
                        title: f.name.replace(/\.[^.]+$/, "").slice(0, 64),
                        markdown: await f.text(),
                        template: "clean",
                      },
                    },
                    2,
                  );
                await open(r.article_id);
              });
              e.target.value = "";
            }}
          />
        </label>
        <label>
          文章
          <select
            aria-label="文章"
            value={aid || ""}
            disabled={busy || saving}
            onChange={(e) => {
              const id = Number(e.target.value);
              if (id) run(() => open(id));
            }}
          >
            <option value="">选择文章</option>
            {items.map((x) => (
              <option key={x.id} value={x.id}>
                {x.title}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary" onClick={() => run(refresh)}>
          刷新列表
        </button>
      </section>
      {!draft ? (
        <section className="empty">
          <h2>直接开始写作，或导入已有文章</h2>
          {items.map((x) => (
            <button
              className="articlecard"
              key={x.id}
              onClick={() => run(() => open(x.id))}
            >
              <strong>{x.title}</strong>
              <span>
                {x.versions.length ? "V" + x.versions[0].number : "工作稿"}
                {x.working_draft?.has_changes ? " · 工作稿有修改" : ""} ·{" "}
                {new Date(x.updated_at * 1000).toLocaleString()}
              </span>
            </button>
          ))}
        </section>
      ) : (
        <>
          <div className="tabs">
            {[
              ["edit", "编辑"],
              ["history", "历史版本"],
              ["wechat", "微信草稿 / 发布记录"],
            ].map(([key, label]) => (
              <button
                key={key}
                className={tab === key ? "" : "secondary"}
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    await flush();
                    setTab(key);
                    if (
                      key === "wechat" &&
                      !version &&
                      article?.versions.length
                    )
                      await pickVersion(article.versions[0].id);
                  })
                }
              >
                {label}
              </button>
            ))}
          </div>
          <section className="toolbar">
            <label className="titlefield">
              文章标题
              <input
                maxLength={64}
                value={draft.title}
                disabled={tab !== "edit" || busy}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, title: e.target.value }))
                }
              />
            </label>
            <label>
              模板
              <select
                aria-label="模板"
                value={draft.template}
                disabled={tab !== "edit" || busy}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, template: e.target.value }))
                }
              >
                {themes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {labels[t.id] || t.id}
                  </option>
                ))}
              </select>
            </label>
            <span className="badge" role="status">
              {saving
                ? "保存中…"
                : dirty
                  ? "有未保存修改"
                  : "已保存 " +
                    new Date(draft.updated_at * 1000).toLocaleTimeString()}
            </span>
          </section>
          <div hidden={tab !== "edit"}>
            <fieldset disabled={navigating} className="editor-controls">
              <div
                className="edit-tools"
                onMouseDown={(e) => {
                  if (e.target.tagName === "BUTTON") e.preventDefault();
                }}
              >
                <button
                  title="撤销"
                  disabled={!editor?.can().undo()}
                  onClick={() => editor.chain().focus().undo().run()}
                >
                  ↶
                </button>
                <button
                  title="重做"
                  disabled={!editor?.can().redo()}
                  onClick={() => editor.chain().focus().redo().run()}
                >
                  ↷
                </button>
                {["bold", "italic", "underline"].map((m, i) => (
                  <button
                    key={m}
                    className={editor?.isActive(m) ? "active" : ""}
                    onClick={() =>
                      editor
                        .chain()
                        .focus()
                        [["toggleBold", "toggleItalic", "toggleUnderline"][i]]()
                        .run()
                    }
                  >
                    {["B", "I", "U"][i]}
                  </button>
                ))}
                <select
                  aria-label="段落类型"
                  value={
                    editor?.isActive("heading")
                      ? editor.getAttributes("heading").level
                      : 0
                  }
                  onChange={(e) =>
                    Number(e.target.value)
                      ? editor
                          .chain()
                          .focus()
                          .setHeading({ level: Number(e.target.value) })
                          .run()
                      : editor.chain().focus().setParagraph().run()
                  }
                >
                  <option value={0}>正文</option>
                  {[1, 2, 3].map((l) => (
                    <option key={l} value={l}>
                      H{l}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() =>
                    editor.chain().focus().toggleBlockquote().run()
                  }
                >
                  引用
                </button>
                <button
                  onClick={() =>
                    editor.chain().focus().toggleBulletList().run()
                  }
                >
                  列表
                </button>
                <button
                  onClick={() =>
                    editor.chain().focus().toggleOrderedList().run()
                  }
                >
                  编号
                </button>
                <button
                  onClick={() => {
                    const href = window.prompt(
                      "链接地址（留空移除）",
                      editor.getAttributes("link").href || "",
                    );
                    if (href === null) return;
                    if (href && !/^(https?:\/\/|mailto:)/i.test(href)) {
                      setError("链接须以 http://、https:// 或 mailto: 开头");
                      return;
                    }
                    href
                      ? editor
                          .chain()
                          .focus()
                          .extendMarkRange("link")
                          .setLink({ href })
                          .run()
                      : editor.chain().focus().unsetLink().run();
                  }}
                >
                  链接
                </button>
                <button
                  onClick={() =>
                    editor.chain().focus().setHorizontalRule().run()
                  }
                >
                  分割线
                </button>
                <button
                  onClick={() => {
                    job.current = null;
                    input.current.click();
                  }}
                >
                  图片
                </button>
                <details className="more-tools">
                  <summary>更多排版</summary>
                  <div>
                    <label>
                      颜色{text.color ? " ●" : ""}
                      <input
                        type="color"
                        value={text.color || "#202c37"}
                        onChange={(e) =>
                          editor.chain().focus().setColor(e.target.value).run()
                        }
                      />
                    </label>
                    {text.color && (
                      <button
                        onClick={() =>
                          editor.chain().focus().unsetColor().run()
                        }
                      >
                        ↺ 颜色
                      </button>
                    )}
                    {choose(
                      "字号" + (text.fontSize ? " ●" : ""),
                      text.fontSize,
                      [12, 14, 16, 18, 20, 24, 28, 32, 36].map((n) => [
                        n + "px",
                        n + "px",
                      ]),
                      (v) =>
                        v
                          ? editor.chain().focus().setFontSize(v).run()
                          : editor.chain().focus().unsetFontSize().run(),
                    )}
                    <label>
                      背景强调{editor?.isActive("highlight") ? " ●" : ""}
                      <input
                        type="color"
                        value={
                          editor?.getAttributes("highlight").color || "#fff3a3"
                        }
                        onChange={(e) =>
                          editor
                            .chain()
                            .focus()
                            .setHighlight({ color: e.target.value })
                            .run()
                        }
                      />
                    </label>
                    {editor?.isActive("highlight") && (
                      <button
                        onClick={() =>
                          editor.chain().focus().unsetHighlight().run()
                        }
                      >
                        ↺ 背景
                      </button>
                    )}
                    {choose(
                      "对齐" + (a.textAlign ? " ●" : ""),
                      a.textAlign,
                      [
                        ["left", "左对齐"],
                        ["center", "居中"],
                        ["right", "右对齐"],
                      ],
                      (v) => attr("textAlign", v),
                    )}
                    {!image &&
                      choose(
                        "段后间距" + (a.spacing ? " ●" : ""),
                        a.spacing,
                        [0, 8, 16, 24].map((n) => [n + "px", n + "px"]),
                        (v) => attr("spacing", v),
                      )}
                    {block === "blockquote" &&
                      choose(
                        "引用样式",
                        a.quoteStyle,
                        [["plain", "简洁"]],
                        (v) => attr("quoteStyle", v),
                      )}
                  </div>
                </details>
                {overridden && <button onClick={reset}>↺ 恢复模板</button>}
              </div>
              {image && (
                <div className="image-tools">
                  <span>已选图片</span>
                  <button
                    onClick={() => {
                      job.current = {
                        replace: true,
                        pos: editor.state.selection.from,
                      };
                      input.current.click();
                    }}
                  >
                    替换
                  </button>
                  <button
                    onClick={() =>
                      editor.chain().focus().deleteSelection().run()
                    }
                  >
                    从文章删除
                  </button>
                  <button
                    onClick={() => {
                      const s = window.prompt("图片说明", a.caption || "");
                      if (s !== null) attr("caption", s);
                    }}
                  >
                    图片说明
                  </button>
                  <button
                    onClick={() => setDraft((d) => ({ ...d, cover: a.src }))}
                  >
                    设为封面
                  </button>
                  {choose(
                    "宽度" + (a.width ? " ●" : ""),
                    a.width,
                    [25, 50, 75, 100].map((n) => [n + "%", n + "%"]),
                    (v) => attr("width", v),
                  )}
                  {choose(
                    "圆角" + (a.borderRadius ? " ●" : ""),
                    a.borderRadius,
                    [0, 4, 8, 12].map((n) => [n + "px", n + "px"]),
                    (v) => attr("borderRadius", v),
                  )}
                </div>
              )}
              <input
                ref={input}
                hidden
                type="file"
                accept="image/png,image/jpeg"
                onChange={(e) => {
                  const f = e.target.files[0];
                  if (f) run(() => upload(f));
                  e.target.value = "";
                }}
              />
              <style>
                {themes.find((t) => t.id === draft.template)?.css || ""}
              </style>
              <div className="rich-editor">
                <EditorContent editor={editor} />
              </div>
              <footer>
                <span>自动保存 ✓</span>
                <button
                  className="secondary"
                  disabled={busy || saving || !dirty}
                  onClick={() => run(flush)}
                >
                  保存修改
                </button>
                <button disabled={busy || saving} onClick={() => run(snapshot)}>
                  保存为 V{(article?.versions[0]?.number || 0) + 1}
                </button>
                <button disabled={busy || saving} onClick={() => run(prepare)}>
                  发送微信草稿 →
                </button>
              </footer>
              <details>
                <summary>素材库 · {assets.length} 张</summary>
                <p>支持 JPG / PNG，每张最大 10MB。删除正文图片只移除引用。历史版本引用的素材不能永久删除。</p>
                <label>
                  封面
                  <select
                    value={draft.cover || ""}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, cover: e.target.value || null }))
                    }
                  >
                    <option value="">未选择</option>
                    {assets.map((a) => (
                      <option key={a.id} value={a.path}>
                        {a.path.slice(-20)}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="asset-grid">
                  {assets.map((a) => (
                    <div key={a.id}>
                      <img
                        src={`${base}/articles/${aid}/assets/${a.path}`}
                        alt="素材"
                      />
                      <button
                        className="secondary"
                        onClick={() =>
                          editor.chain().focus().setImage({ src: a.path }).run()
                        }
                      >
                        插入
                      </button>
                      <button
                        className="danger"
                        onClick={() => {
                          if (window.confirm("永久删除这张素材？"))
                            run(async () => {
                              await flush();
                              await api(
                                `/articles/${aid}/assets/${a.id}`,
                                { method: "DELETE" },
                                2,
                              );
                              await material();
                            });
                        }}
                      >
                        永久删除
                      </button>
                    </div>
                  ))}
                </div>
              </details>
            </fieldset>
          </div>
          {tab === "history" && (
            <section className="empty">
              <h2>不可变历史版本</h2>
              {article?.versions.map((v) => (
                <button
                  className="articlecard"
                  key={v.id}
                  onClick={() => run(() => pickVersion(v.id))}
                >
                  V{v.number} · {v.title} · {labels[v.template]}
                </button>
              ))}
              {version && (
                <>
                  <h3>
                    V{version.number} · {version.title}
                  </h3>
                  <iframe
                    className="final-frame"
                    title="历史版本只读预览"
                    sandbox="allow-same-origin"
                    srcDoc={frame(version.preview_html)}
                  />
                  <button
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        await flush();
                        const d = await api(
                          `/articles/${aid}/restore/${version.id}`,
                          {
                            method: "POST",
                            body: { revision: live.current.revision },
                          },
                          2,
                        );
                        setDraft(d);
                        live.current = d;
                        ack.current = stamp(d);
                        setSaved(ack.current);
                        editor.commands.setContent(d.content_json, {
                          emitUpdate: false,
                        });
                        setTab("edit");
                        await material();
                        setNotice("旧版本已复制为工作稿");
                      })
                    }
                  >
                    恢复为工作稿
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => run(prepare)}
                  >
                    发送此版本到微信
                  </button>
                </>
              )}
            </section>
          )}
          {tab === "preview" && preview && (
            <section className="empty">
              <h2>微信发送预览 · V{version?.number}</h2>
              <p>
                模板：{labels[version?.template]} ·
                下方为准备提交给微信的最终内容。
              </p>
              <iframe
                className="final-frame"
                title="微信发送前最终预览"
                sandbox="allow-same-origin"
                srcDoc={frame(preview.html)}
              />
              <footer>
                <button className="secondary" onClick={() => setTab("edit")}>
                  返回修改
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      await api(
                        `/versions/${preview.vid}/send`,
                        {
                          method: "POST",
                          body: { html_hash: preview.html_hash },
                        },
                        2,
                      );
                      await pickVersion(preview.vid);
                      setTab("wechat");
                      setNotice("微信草稿已创建，请取回确认");
                    })
                  }
                >
                  确认发送微信草稿
                </button>
              </footer>
            </section>
          )}
          {tab === "wechat" && (
            <section className="empty">
              <h2>微信草稿与发布记录</h2>
              <select
                value={version?.id || ""}
                onChange={(e) => {
                  const id = e.target.value;
                  if (id) run(() => pickVersion(id));
                }}
              >
                <option value="">选择版本</option>
                {article?.versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    V{v.number} · {v.title}
                  </option>
                ))}
              </select>
              {version?.publication ? (
                <>
                  <p>
                    V{version.number} ·{" "}
                    {statuses[version.publication.status] ||
                      version.publication.status}
                  </p>
                  <footer>
                    {version.publication.draft_media_id && (
                      <button
                        disabled={busy}
                        onClick={() => run(() => action("/draft/check"))}
                      >
                        取回微信草稿
                      </button>
                    )}
                    {version.publication.status === "prepared" && (
                      <button disabled={busy} onClick={() => run(prepare)}>
                        查看最终预览
                      </button>
                    )}
                    {user.role === "ADMIN" &&
                      version.publication.status === "draft" &&
                      version.publication.html_returned && (
                        <button
                          className="danger"
                          disabled={busy}
                          onClick={() => {
                            if (
                              window.confirm(
                                `确认正式发布《${version.title}》V${version.number}？`,
                              )
                            )
                              run(async () => {
                                await api(`/versions/${version.id}/publish`, {
                                  method: "POST",
                                  body: { confirm_version_id: version.id },
                                });
                                await pickVersion(version.id);
                                setNotice("已提交微信处理，请查询发布结果");
                              });
                          }}
                        >
                          正式发布
                        </button>
                      )}
                    {version.publication.publish_id && (
                      <button
                        disabled={busy}
                        onClick={() => run(() => action("/publish/check"))}
                      >
                        查询发布结果
                      </button>
                    )}
                  </footer>
                  <div className="tabs">
                    {[
                      ["returned", "微信返回版本"],
                      ["sent", "发送给微信版本"],
                      ["diff", "HTML 差异"],
                    ].map(([key, label]) => (
                      <button
                        className={view === key ? "" : "secondary"}
                        key={key}
                        onClick={() => setView(key)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  {view === "diff" ? (
                    <pre>{diff || "没有差异或尚未取回草稿"}</pre>
                  ) : (
                    <iframe
                      className="final-frame"
                      title="微信文章预览"
                      sandbox="allow-same-origin"
                      srcDoc={frame(
                        view === "returned"
                          ? version.publication.html_returned ||
                              "<p>请先取回微信草稿</p>"
                          : version.publication.html_sent || "",
                      )}
                    />
                  )}
                  <details>
                    <summary>发布详情</summary>
                    <pre>{version.publication.result || "暂无结果"}</pre>
                  </details>
                </>
              ) : (
                <p>此版本尚未发送微信草稿。</p>
              )}
            </section>
          )}
        </>
      )}
      {creating && (
        <div className="modalback">
          <form
            className="modal"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.target);
              run(async () => {
                await flush();
                const r = await api(
                  "/articles",
                  { method: "POST", body: Object.fromEntries(f) },
                  2,
                );
                setCreating(false);
                await open(r.article_id);
              });
            }}
          >
            <h2>新建文章</h2>
            <label>
              标题
              <input name="title" required maxLength={64} autoFocus />
            </label>
            <label>
              模板
              <select name="template" defaultValue="clean">
                {themes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {labels[t.id] || t.id}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="secondary"
              onClick={() => setCreating(false)}
            >
              取消
            </button>
            <button disabled={busy}>开始写作</button>
          </form>
        </div>
      )}
    </>
  );
}
