import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
const Workspace = React.lazy(() => import("./editor.jsx"));
import "./style.css";
const apiBase = import.meta.env.BASE_URL + "api/";
function App() {
  const [user, setUser] = useState(null),
    [checked, setChecked] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [tab, setTab] = useState("articles"),
    [management, setManagement] = useState(null),
    [shownToken, setShownToken] = useState("");
  const exitRef = useRef(null);
  async function api(path, options = {}, version = 1) {
    const headers = { "x-csrf-token": user?.csrf || "", ...options.headers },
      request = { ...options, headers, credentials: "same-origin" };
    if (options.body && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      request.body = JSON.stringify(options.body);
    }
    const r = await fetch(apiBase + "v" + version + path, request),
      data = await r.json();
    if (!r.ok) {
      if (r.status === 401) setUser(null);
      const e = Error(
        typeof data.detail === "string" ? data.detail : "请检查填写的内容",
      );
      e.status = r.status;
      throw e;
    }
    return data;
  }
  async function run(fn) {
    setError("");
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    fetch(apiBase + "v1/me")
      .then(async (r) => {
        if (r.ok) setUser(await r.json());
      })
      .finally(() => setChecked(true));
  }, []);
  if (!checked) return <main className="login">正在连接…</main>;
  if (!user)
    return (
      <main className="login">
        <div className="brand">WORKFLOW HUB / PUBLISHER V2</div>
        <h1>公众号发布工作台</h1>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const d = new FormData(e.target);
            run(async () =>
              setUser(
                await api("/login", {
                  method: "POST",
                  body: Object.fromEntries(d),
                }),
              ),
            );
          }}
        >
          <label>
            用户名
            <input name="username" autoComplete="username" required />
          </label>
          <label>
            密码
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <button disabled={busy}>登录</button>
        </form>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </main>
    );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          WORKFLOW
          <br />
          HUB <span>/ 公众号 V2</span>
        </div>
        <nav>
          <button
            className={tab === "articles" ? "active" : ""}
            onClick={() => setTab("articles")}
          >
            文章工作台
          </button>
          {user.role === "ADMIN" && (
            <button
              className={tab === "admin" ? "active" : ""}
              onClick={() =>
                run(async () => {
                  await exitRef.current?.();
                  setManagement(await api("/admin"));
                  setTab("admin");
                })
              }
            >
              系统管理
            </button>
          )}
        </nav>
        <div className="account">
          <strong>{user.username}</strong>
          <small>{user.role === "ADMIN" ? "管理员" : "编辑"}</small>
          <button
            disabled={busy}
            onClick={() =>
              run(async () => {
                await exitRef.current?.();
                await api("/logout", { method: "POST" });
                setUser(null);
                setShownToken("");
              })
            }
          >
            退出登录
          </button>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <small>
              内容管理 / {tab === "articles" ? "编辑与发布" : "管理"}
            </small>
            <h1>{tab === "articles" ? "文章工作台" : "系统管理"}</h1>
          </div>
        </header>
        {error && (
          <div role="alert" className="error">
            {error}
          </div>
        )}
        <div hidden={tab !== "articles"}>
          <React.Suspense fallback={<p>正在加载编辑器…</p>}>
            <Workspace api={api} user={user} exitRef={exitRef} />
          </React.Suspense>
        </div>
        <div hidden={tab !== "admin"}>
          {management && (
            <div className="admin">
              <section>
                <h2>公众号配置</h2>
                <p>
                  AppID：{management.wechat.app_id || "未配置"}　AppSecret：
                  {management.wechat.secret_configured ? "已配置" : "未配置"}
                  　正式发布：
                  {management.wechat.publish_enabled ? "启用" : "关闭"}
                </p>
              </section>
              <section>
                <h2>用户管理</h2>
                <form
                  className="inlineform"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = e.target;
                    const body = Object.fromEntries(new FormData(f));
                    run(async () => {
                      await api("/admin/users", { method: "POST", body });
                      f.reset();
                      setManagement(await api("/admin"));
                    });
                  }}
                >
                  <label>
                    用户名
                    <input name="username" required />
                  </label>
                  <label>
                    初始密码
                    <input
                      name="password"
                      type="password"
                      minLength={12}
                      required
                    />
                  </label>
                  <label>
                    角色
                    <select name="role">
                      <option>EDITOR</option>
                      <option>ADMIN</option>
                    </select>
                  </label>
                  <button disabled={busy}>创建用户</button>
                </form>
                <div className="tablewrap">
                  <table>
                    <thead>
                      <tr>
                        <th>用户</th>
                        <th>角色</th>
                        <th>状态</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {management.users.map((u) => (
                        <tr key={u.id}>
                          <td>{u.username}</td>
                          <td>{u.role}</td>
                          <td>{u.status}</td>
                          <td>
                            {u.username !== user.username && (
                              <>
                                <button
                                  className="secondary"
                                  onClick={() =>
                                    run(async () => {
                                      await api(
                                        "/admin/users/" + u.id + "/status",
                                        {
                                          method: "POST",
                                          body: {
                                            status:
                                              u.status === "active"
                                                ? "disabled"
                                                : "active",
                                          },
                                        },
                                      );
                                      setManagement(await api("/admin"));
                                    })
                                  }
                                >
                                  {u.status === "active" ? "禁用" : "启用"}
                                </button>
                                <button
                                  className="secondary"
                                  onClick={() => {
                                    if (
                                      window.confirm(
                                        "删除用户 " + u.username + "？",
                                      )
                                    )
                                      run(async () => {
                                        await api("/admin/users/" + u.id, {
                                          method: "DELETE",
                                        });
                                        setManagement(await api("/admin"));
                                      });
                                  }}
                                >
                                  删除
                                </button>
                              </>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <section>
                <h2>GitHub 上传 Token</h2>
                <p>仅允许上传文章。完整 Token 只在创建后显示一次。</p>
                <form
                  className="inlineform"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const d = new FormData(e.target);
                    run(async () => {
                      const r = await api("/admin/tokens", {
                        method: "POST",
                        body: {
                          name: d.get("name"),
                          days: Number(d.get("days")),
                        },
                      });
                      setShownToken(r.token);
                      setManagement(await api("/admin"));
                    });
                  }}
                >
                  <label>
                    名称
                    <input name="name" placeholder="github-actions" required />
                  </label>
                  <label>
                    有效天数
                    <input
                      name="days"
                      type="number"
                      min={1}
                      max={365}
                      defaultValue={90}
                    />
                  </label>
                  <button disabled={busy}>创建 Token</button>
                </form>
                {shownToken && (
                  <div className="notice">
                    <label>
                      复制到 GitHub 的 PUBLISHER_UPLOAD_TOKEN
                      <input readOnly value={shownToken} />
                    </label>
                    <button onClick={() => setShownToken("")}>
                      已保存，隐藏
                    </button>
                  </div>
                )}
                <div className="tablewrap">
                  <table>
                    <thead>
                      <tr>
                        <th>名称</th>
                        <th>前缀</th>
                        <th>有效至</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {management.tokens.map((t) => (
                        <tr key={t.id}>
                          <td>{t.name}</td>
                          <td>{t.prefix}…</td>
                          <td>
                            {new Date(t.expires_at * 1000).toLocaleDateString()}
                          </td>
                          <td>
                            {t.revoked_at ? (
                              "已吊销"
                            ) : (
                              <button
                                className="secondary"
                                onClick={() => {
                                  if (window.confirm("吊销该上传Token？"))
                                    run(async () => {
                                      await api("/admin/tokens/" + t.id, {
                                        method: "DELETE",
                                      });
                                      setManagement(await api("/admin"));
                                    });
                                }}
                              >
                                吊销
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
              <section>
                <h2>最近操作</h2>
                <div className="tablewrap">
                  <table>
                    <thead>
                      <tr>
                        <th>时间</th>
                        <th>操作者</th>
                        <th>动作</th>
                        <th>对象</th>
                      </tr>
                    </thead>
                    <tbody>
                      {management.logs.map((l) => (
                        <tr key={l.id}>
                          <td>
                            {new Date(l.created_at * 1000).toLocaleString()}
                          </td>
                          <td>{l.actor}</td>
                          <td>{l.action}</td>
                          <td>{l.target}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);
