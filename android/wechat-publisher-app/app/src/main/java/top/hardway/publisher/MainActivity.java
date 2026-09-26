package top.hardway.publisher;

import android.app.Activity;
import android.annotation.SuppressLint;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.window.OnBackInvokedDispatcher;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

import java.util.HashMap;
import java.util.Map;

public final class MainActivity extends Activity {
    private static final String START_URL = "https://stocklab.hardway.top/publisher/";
    private static final String AUTO_LOGIN_URL = "https://stocklab.hardway.top/publisher/api/v1/app-login";
    private static final int FILE_CHOOSER_REQUEST = 2001;

    private WebView webView;
    private ProgressBar progressBar;
    private ValueCallback<Uri[]> fileCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            root.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                return WindowInsets.CONSUMED;
            });
        }

        webView = new WebView(this);
        webView.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        FrameLayout.LayoutParams progressParams = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(3));
        progressParams.gravity = android.view.Gravity.TOP;
        progressBar.setLayoutParams(progressParams);

        root.addView(webView);
        root.addView(progressBar);
        setContentView(root);

        configureWebView();
        configureBackNavigation();

        if (savedInstanceState == null) {
            loadAppSession();
        } else {
            webView.restoreState(savedInstanceState);
        }
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportMultipleWindows(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setUserAgentString(settings.getUserAgentString() + " WorkflowHubPublisher/1.0");

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            settings.setSafeBrowsingEnabled(true);
        }

        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, false);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame()) {
                    return false;
                }
                String url = request.getUrl().toString();
                if ("workflowhub".equals(request.getUrl().getScheme()) && "reauth".equals(request.getUrl().getHost())) {
                    loadAppSession();
                    return true;
                }
                if (PublisherUrlPolicy.isAllowed(url)) {
                    return false;
                }
                openExternal(url);
                return true;
            }

            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel();
                Toast.makeText(MainActivity.this, R.string.ssl_error, Toast.LENGTH_LONG).show();
            }

            @Override
            public void onReceivedHttpError(
                    WebView view,
                    WebResourceRequest request,
                    WebResourceResponse errorResponse) {
                if (!request.isForMainFrame()) {
                    return;
                }
                String failedUrl = request.getUrl().toString();
                if (AUTO_LOGIN_URL.equals(failedUrl) && errorResponse.getStatusCode() >= 400) {
                    showAutoLoginError(errorResponse.getStatusCode());
                    return;
                }
                if (errorResponse.getStatusCode() >= 500) {
                    Toast.makeText(MainActivity.this, R.string.server_error, Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progressBar.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE);
                progressBar.setProgress(newProgress);
            }

            @Override
            public boolean onShowFileChooser(
                    WebView webView,
                    ValueCallback<Uri[]> newCallback,
                    FileChooserParams fileChooserParams) {
                if (fileCallback != null) {
                    fileCallback.onReceiveValue(null);
                }
                fileCallback = newCallback;

                Intent intent;
                try {
                    intent = fileChooserParams.createIntent();
                } catch (Exception ex) {
                    intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType("image/*");
                }

                try {
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                    return true;
                } catch (ActivityNotFoundException ex) {
                    fileCallback = null;
                    Toast.makeText(MainActivity.this, R.string.no_file_picker, Toast.LENGTH_LONG).show();
                    return false;
                }
            }
        });

        webView.setDownloadListener((url, userAgent, contentDisposition, mimetype, contentLength) ->
                openExternal(url));
    }

    private void loadAppSession() {
        String token = BuildConfig.PUBLISHER_APP_TOKEN;
        if (token == null || token.isEmpty()) {
            showAutoLoginError(0);
            return;
        }
        Map<String, String> headers = new HashMap<>();
        headers.put("X-Publisher-App-Token", token);
        progressBar.setVisibility(View.VISIBLE);
        webView.loadUrl(AUTO_LOGIN_URL, headers);
    }

    private void showAutoLoginError(int statusCode) {
        String detail = statusCode == 0
                ? "APK 没有自动登录凭证。"
                : "服务器尚未启用此 APK 的自动登录凭证（HTTP " + statusCode + "）。";
        String html = "<!doctype html><html><head><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                + "<style>body{font-family:sans-serif;padding:28px;line-height:1.7;color:#182c43}"
                + "h2{margin-top:0}code{word-break:break-all;background:#f1f5f9;padding:2px 5px}</style></head><body>"
                + "<h2>公众号发布 App</h2><p>" + detail + "</p>"
                + "<p>请先把与这个 APK 同批生成的 <code>publisher-android.env</code> 配置到服务器并部署新版 Publisher。</p>"
                + "</body></html>";
        webView.loadDataWithBaseURL(START_URL, html, "text/html", "utf-8", null);
    }

    private void openExternal(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (ActivityNotFoundException ex) {
            Toast.makeText(this, R.string.no_browser, Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == FILE_CHOOSER_REQUEST && fileCallback != null) {
            Uri[] result = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
            fileCallback.onReceiveValue(result);
            fileCallback = null;
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    private void configureBackNavigation() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT,
                    this::handleBack);
        }
    }

    private void handleBack() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            finish();
        }
    }

    @SuppressLint("GestureBackNavigation")
    @Override
    public void onBackPressed() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            handleBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (fileCallback != null) {
            fileCallback.onReceiveValue(null);
            fileCallback = null;
        }
        if (webView != null) {
            webView.stopLoading();
            webView.loadUrl("about:blank");
            webView.clearHistory();
            webView.removeAllViews();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
