import { test, expect } from "@playwright/test";
import path from "node:path";
async function login(page) {
  await page.goto("/");
  await page.getByLabel("用户名").fill("admin");
  await page.getByLabel("密码").fill("browser-test-password");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.getByRole("button", { name: "＋ 新建文章" }).waitFor();
}
async function create(page, title) {
  await page.getByRole("button", { name: "＋ 新建文章" }).click();
  await page.getByRole("textbox", { name: "标题", exact: true }).fill(title);
  await page.getByRole("button", { name: "开始写作" }).click();
  await expect(page.getByLabel("文章标题", { exact: true })).toHaveValue(title);
  await expect(page.getByLabel("文章标题", { exact: true })).toBeEnabled();
  await expect(page.locator(".tiptap")).toHaveAttribute(
    "contenteditable",
    "true",
  );
}
async function saved(page) {
  await expect(
    page.getByRole("status").filter({ hasText: /^已保存 / }),
  ).toBeVisible();
}
test("autosave, immutable history, override reset and mobile layout", async ({
  page,
}) => {
  await login(page);
  await create(page, "Browser acceptance");
  const editor = page.locator(".tiptap");
  await editor.click();
  await page.keyboard.type("Hello browser");
  await saved(page);
  await page.getByRole("button", { name: "保存为 V1", exact: true }).click();
  await expect(page.getByText("已保存为 V1", { exact: true })).toBeVisible();
  await page.reload();
  await page
    .getByLabel("文章", { exact: true })
    .selectOption({ label: "Browser acceptance" });
  await expect(editor).toContainText("Hello browser");
  await page.locator(".more-tools summary").click();
  await editor.click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.locator("input[type=color]").first().fill("#ff0000");
  await page.getByLabel("模板", { exact: true }).selectOption("tech");
  await saved(page);
  await expect(editor.locator("span[style]")).toHaveCSS(
    "color",
    "rgb(255, 0, 0)",
  );
  await page.getByRole("button", { name: "↺ 恢复模板", exact: true }).click();
  await saved(page);
  await expect(editor.locator("span[style]")).toHaveCount(0);
  // Type while snapshot is in flight; the acknowledged revision must not overwrite new edits.
  await page.route("**/api/v2/articles/*/versions", async (route) => {
    await new Promise((r) => setTimeout(r, 2600));
    await route.continue();
  });
  await page.getByRole("button", { name: "保存为 V2", exact: true }).click();
  await editor.click();
  await page.keyboard.press("End");
  await page.keyboard.type(" while saving");
  await expect(page.getByText("已保存为 V2", { exact: true })).toBeVisible();
  await saved(page);
  await expect(editor).toContainText("while saving");
  await page.getByRole("button", { name: "历史版本", exact: true }).click();
  await page.getByRole("button", { name: /V1 · Browser acceptance/ }).click();
  await page.getByRole("button", { name: "恢复为工作稿", exact: true }).click();
  await expect(editor).toHaveText("Hello browser");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
test("image caption, final confirmation and WeChat returned preview", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page);
  await create(page, "Image acceptance");
  const editor = page.locator(".tiptap");
  await editor.click();
  await page.keyboard.type("Image article");
  await page
    .locator('input[type=file][accept="image/png,image/jpeg,image/webp"]')
    .setInputFiles(
      path.resolve("../../inputs/wechat/acceptance/images/portrait.png"),
    );
  await expect(editor.locator("img")).toBeVisible();
  await editor.locator("img").click();
  page.once("dialog", (dialog) => dialog.accept("Image caption"));
  await page.getByRole("button", { name: "图片说明", exact: true }).click();
  await expect(editor.locator("figcaption")).toHaveText("Image caption");
  await saved(page);
  await page.getByRole("button", { name: "发送微信草稿 →" }).click();
  await expect(
    page.getByRole("heading", { name: /微信发送预览/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "确认发送微信草稿" }),
  ).toBeVisible();
  const preview = page
    .locator("section.empty")
    .filter({ has: page.getByRole("heading", { name: /微信发送预览/ }) });
  await preview
    .getByText("查看微信图片副本 / 原图对比", { exact: true })
    .click();
  const copies = preview.getByAltText(/微信正文副本|微信封面副本/);
  await expect(copies).toHaveCount(2);
  for (const copy of await copies.all()) {
    await expect(copy).toBeVisible();
    await expect
      .poll(() => copy.evaluate((img) => img.naturalWidth))
      .toBeGreaterThan(0);
  }
  await expect(preview.getByText(/已满足大小限制/)).toHaveCount(2);
  await page.getByRole("button", { name: "确认发送微信草稿" }).click();
  await page.getByRole("button", { name: "取回微信草稿" }).click();
  await expect(
    page.frameLocator('iframe[title="微信文章预览"]').locator("figcaption"),
  ).toHaveText("Image caption");
  await page.getByRole("button", { name: "HTML 差异", exact: true }).click();
  await expect(page.getByText("没有差异或尚未取回草稿")).toBeVisible();
  expect(errors).toEqual([]);
});

test("conflict reload synchronizes the visible document", async ({ page }) => {
  await login(page);
  await create(page, "Conflict acceptance");
  const editor = page.locator(".tiptap");
  await editor.click();
  await page.keyboard.type("Original");
  await saved(page);
  await page.evaluate(async () => {
    const me = await (await fetch("/api/v1/me")).json(),
      all = await (await fetch("/api/v1/articles")).json(),
      id = all.find((a) => a.title === "Conflict acceptance").id,
      d = await (await fetch(`/api/v2/articles/${id}/draft`)).json();
    await fetch(`/api/v2/articles/${id}/draft`, {
      method: "PUT",
      headers: { "content-type": "application/json", "x-csrf-token": me.csrf },
      body: JSON.stringify({
        ...d,
        content_json: {
          type: "doc",
          content: [
            {
              type: "paragraph",
              content: [{ type: "text", text: "Remote update" }],
            },
          ],
        },
      }),
    });
  });
  await editor.click();
  await page.keyboard.press("End");
  await page.keyboard.type(" Local rejected");
  await expect(page.getByRole("alert")).toContainText("工作稿已被其他窗口修改");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "重新读取", exact: true }).click();
  await expect(editor).toHaveText("Remote update");
  await editor.click();
  await page.keyboard.press("End");
  await page.keyboard.type(" continued");
  await saved(page);
  await expect(editor).toHaveText("Remote update continued");
});

test("navigation pauses editing while the next draft loads", async ({
  page,
}) => {
  await login(page);
  await create(page, "Navigation first");
  await page.locator(".tiptap").click();
  await page.keyboard.type("Keep first draft");
  await saved(page);
  // Creation keeps the previous editor mounted while the new draft is fetched.
  await page.route("**/api/v2/articles/*/draft", async (route) => {
    if (route.request().method() === "GET")
      await new Promise((r) => setTimeout(r, 1200));
    await route.continue();
  });
  await create(page, "Navigation second");
  await page.locator(".tiptap").click();
  await page.keyboard.type("Second draft");
  await expect(page.locator(".tiptap")).toHaveText("Second draft");
  await saved(page);
  await page.unroute("**/api/v2/articles/*/draft");
  await page
    .getByLabel("文章", { exact: true })
    .selectOption({ label: "Navigation first" });
  await expect(page.locator(".tiptap")).toHaveText("Keep first draft");
  await page.route("**/api/v2/articles/*/draft", async (route) => {
    if (route.request().method() === "GET")
      await new Promise((r) => setTimeout(r, 1200));
    await route.continue();
  });
  await page
    .getByLabel("文章", { exact: true })
    .selectOption({ label: "Navigation second" });
  await expect(page.locator(".tiptap")).toHaveAttribute(
    "contenteditable",
    "false",
  );
  await expect(
    page.getByRole("button", { name: "↶", exact: true }),
  ).toBeDisabled();
  await expect(page.locator(".tiptap")).toHaveText("Second draft");
  await page.unroute("**/api/v2/articles/*/draft");
  await page
    .getByLabel("文章", { exact: true })
    .selectOption({ label: "Navigation first" });
  await expect(page.locator(".tiptap")).toHaveText("Keep first draft");
});

test("snapshot never adopts another window revision without its content", async ({
  page,
}) => {
  await login(page);
  await create(page, "Snapshot conflict");
  const editor = page.locator(".tiptap");
  await editor.click();
  await page.keyboard.type("Local snapshot");
  await saved(page);
  await page.route("**/api/v2/articles/*/versions", async (route) => {
    const response = await route.fetch();
    await page.evaluate(async () => {
      const me = await (await fetch("/api/v1/me")).json(),
        articles = await (await fetch("/api/v1/articles")).json(),
        id = articles.find((a) => a.title === "Snapshot conflict").id,
        d = await (await fetch(`/api/v2/articles/${id}/draft`)).json();
      const r = await fetch(`/api/v2/articles/${id}/draft`, {
        method: "PUT",
        headers: {
          "content-type": "application/json",
          "x-csrf-token": me.csrf,
        },
        body: JSON.stringify({
          ...d,
          content_json: {
            type: "doc",
            content: [
              {
                type: "paragraph",
                content: [{ type: "text", text: "Remote after snapshot" }],
              },
            ],
          },
        }),
      });
      if (!r.ok) throw Error("Remote save failed");
    });
    await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "保存为 V1", exact: true }).click();
  await expect(page.getByText("已保存为 V1", { exact: true })).toBeVisible();
  await editor.click();
  await page.keyboard.press("End");
  await page.keyboard.type(" next local edit");
  await expect(page.getByRole("alert")).toContainText("工作稿已被其他窗口修改");
  const remote = await page.evaluate(async () => {
    const articles = await (await fetch("/api/v1/articles")).json(),
      id = articles.find((a) => a.title === "Snapshot conflict").id;
    return await (await fetch(`/api/v2/articles/${id}/draft`)).json();
  });
  expect(JSON.stringify(remote.content_json)).toContain(
    "Remote after snapshot",
  );
});
