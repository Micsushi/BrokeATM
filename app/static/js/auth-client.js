(function () {
  const state = {
    loaded: false,
    config: null,
    client: null,
  };

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[src="${src}"]`)) {
        resolve();
        return;
      }
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  async function init() {
    if (state.loaded) return state;
    const res = await fetch("/api/runtime/config", { credentials: "same-origin" });
    state.config = await res.json();
    if (
      state.config.deployment_mode === "cloud" &&
      state.config.auth_mode === "supabase" &&
      state.config.supabase_url &&
      state.config.supabase_anon_key
    ) {
      // Vendored SDK — avoids CDN SRI issues with dynamically-generated builds.
      // Update the version in both this path and the filename when upgrading.
      if (!window.supabase) {
        await loadScript("/static/js/supabase-2.49.4.min.js");
      }
      state.client = window.supabase.createClient(
        state.config.supabase_url,
        state.config.supabase_anon_key
      );
    }
    state.loaded = true;
    return state;
  }

  async function getAccessToken() {
    await init();
    if (!state.client) return null;
    const { data } = await state.client.auth.getSession();
    return data.session?.access_token || null;
  }

  async function requireSession() {
    await init();
    if (!state.client) return null;
    const { data } = await state.client.auth.getSession();
    if (!data.session && location.pathname !== "/login") {
      location.href = `/login?next=${encodeURIComponent(location.pathname + location.search)}`;
    }
    return data.session;
  }

  async function signOut() {
    await init();
    if (state.client) await state.client.auth.signOut();
    location.href = "/login";
  }

  const originalFetch = window.fetch.bind(window);
  window.fetch = async function (input, initOptions) {
    const url = typeof input === "string" ? input : input.url;
    const isApi = url && (url.startsWith("/api/") || url.startsWith(location.origin + "/api/"));
    if (!isApi || url.includes("/api/runtime/config")) {
      return originalFetch(input, initOptions);
    }

    const token = await getAccessToken();
    const nextInit = initOptions ? { ...initOptions } : {};
    const headers = new Headers(nextInit.headers || (typeof input !== "string" ? input.headers : undefined));
    if (token) headers.set("Authorization", `Bearer ${token}`);
    nextInit.headers = headers;

    const response = await originalFetch(input, nextInit);
    if (response.status === 401 && state.config?.deployment_mode === "cloud") {
      location.href = `/login?next=${encodeURIComponent(location.pathname + location.search)}`;
    }
    return response;
  };

  window.BrokeATMAuth = {
    init,
    requireSession,
    signOut,
    getAccessToken,
    get client() {
      return state.client;
    },
    get config() {
      return state.config;
    },
  };
})();
