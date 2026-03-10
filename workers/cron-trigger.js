/**
 * Cloudflare Worker — HIROKI AI Empire Cron Trigger
 *
 * Render.com 上の inquiry_bot サーバーに対して
 * cron スケジュールでトリガーAPIを呼び出す。
 * cron-job.org の完全置き換え。
 *
 * 環境変数（wrangler secret put で設定）:
 *   RENDER_APP_URL  — Render アプリURL
 *   TRIGGER_SECRET  — トリガーAPI認証シークレット
 */

/** cron 式とトリガーAPIのマッピング */
const CRON_MAP = [
  {
    cron: "*/14 * * * *",
    endpoint: "/api/keep-alive",
    method: "GET",
    name: "keep-alive",
  },
  {
    cron: "30 9 * * *",
    endpoint: "/api/trigger/daily-post",
    method: "POST",
    name: "daily-post (18:30 JST)",
  },
  {
    cron: "0 12 * * *",
    endpoint: "/api/trigger/daily-analysis",
    method: "POST",
    name: "daily-analysis (21:00 JST)",
  },
  {
    cron: "0 22 * * *",
    endpoint: "/api/trigger/daily-collect",
    method: "POST",
    name: "daily-collect (07:00 JST)",
  },
  {
    cron: "0 0 * * 1",
    endpoint: "/api/trigger/weekly-analysis",
    method: "POST",
    name: "weekly-analysis (月曜 09:00 JST)",
  },
  {
    cron: "0 23 * * 0",
    endpoint: "/api/trigger/weekly-tech",
    method: "POST",
    name: "weekly-tech (月曜 08:00 JST)",
  },
];

/**
 * Render アプリにリクエストを送信
 * @param {string} baseUrl
 * @param {string} endpoint
 * @param {string} method
 * @param {string} secret
 * @returns {Promise<{ok: boolean, status: number, body: string}>}
 */
async function callRenderApp(baseUrl, endpoint, method, secret) {
  const url = `${baseUrl}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    "X-Trigger-Secret": secret,
  };

  const response = await fetch(url, { method, headers });
  const body = await response.text();

  return {
    ok: response.ok,
    status: response.status,
    body,
  };
}

export default {
  /**
   * Cron Trigger ハンドラー
   * wrangler.toml の [triggers].crons に対応
   */
  async scheduled(event, env, ctx) {
    const cronExpression = event.cron;
    const renderUrl = env.RENDER_APP_URL;
    const triggerSecret = env.TRIGGER_SECRET || "";

    if (!renderUrl) {
      console.error("RENDER_APP_URL is not set");
      return;
    }

    // cron 式にマッチするタスクを実行
    const tasks = CRON_MAP.filter((t) => t.cron === cronExpression);

    if (tasks.length === 0) {
      console.warn(`No task mapped for cron: ${cronExpression}`);
      return;
    }

    for (const task of tasks) {
      console.log(`[${task.name}] Triggering ${task.method} ${task.endpoint}`);

      try {
        const result = await callRenderApp(
          renderUrl,
          task.endpoint,
          task.method,
          triggerSecret,
        );

        if (result.ok) {
          console.log(`[${task.name}] Success (${result.status}): ${result.body}`);
        } else {
          console.error(
            `[${task.name}] Failed (${result.status}): ${result.body}`,
          );
        }
      } catch (error) {
        console.error(`[${task.name}] Error: ${error.message}`);
      }
    }
  },

  /**
   * HTTP リクエストハンドラー（手動テスト・ステータス確認用）
   */
  async fetch(request, env) {
    const url = new URL(request.url);

    // ステータスページ
    if (url.pathname === "/" || url.pathname === "/status") {
      const renderUrl = env.RENDER_APP_URL || "(not set)";
      const hasSecret = env.TRIGGER_SECRET ? "configured" : "not set";

      return new Response(
        JSON.stringify(
          {
            service: "HIROKI AI Empire — Cron Trigger Worker",
            render_app: renderUrl,
            trigger_secret: hasSecret,
            cron_tasks: CRON_MAP.map((t) => ({
              name: t.name,
              cron: t.cron,
              endpoint: t.endpoint,
            })),
          },
          null,
          2,
        ),
        {
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    // 手動トリガー: /trigger/<task-name>
    if (url.pathname.startsWith("/trigger/")) {
      const taskName = url.pathname.replace("/trigger/", "");
      const task = CRON_MAP.find(
        (t) => t.name.split(" ")[0] === taskName,
      );

      if (!task) {
        return new Response(
          JSON.stringify({ error: `Unknown task: ${taskName}` }),
          { status: 404, headers: { "Content-Type": "application/json" } },
        );
      }

      const renderUrl = env.RENDER_APP_URL;
      const triggerSecret = env.TRIGGER_SECRET || "";

      if (!renderUrl) {
        return new Response(
          JSON.stringify({ error: "RENDER_APP_URL not configured" }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      }

      try {
        const result = await callRenderApp(
          renderUrl,
          task.endpoint,
          task.method,
          triggerSecret,
        );

        return new Response(
          JSON.stringify({
            task: task.name,
            result: {
              ok: result.ok,
              status: result.status,
              body: result.body,
            },
          }),
          {
            status: result.ok ? 200 : 502,
            headers: { "Content-Type": "application/json" },
          },
        );
      } catch (error) {
        return new Response(
          JSON.stringify({ task: task.name, error: error.message }),
          { status: 502, headers: { "Content-Type": "application/json" } },
        );
      }
    }

    return new Response("Not Found", { status: 404 });
  },
};
