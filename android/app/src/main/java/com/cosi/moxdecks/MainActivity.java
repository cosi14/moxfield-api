package com.cosi.moxdecks;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.Toast;

/** Envoltorio WebView del front. La URL del servidor se guarda y se puede cambiar desde el menú. */
public class MainActivity extends Activity {
    private static final String PREFS = "cfg";
    private static final String KEY_URL = "server_url";

    private WebView web;
    private SharedPreferences prefs;
    private String serverHost = "";

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);

        web = new WebView(this);
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if (serverHost.equals(u.getHost())) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, u)); // moxfield.com y demás, al navegador
                return true;
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame()) {
                    v.loadData("<meta name='viewport' content='width=device-width'><body style='font-family:sans-serif;padding:24px'>"
                            + "<h3>No se pudo conectar</h3><p>" + e.getDescription() + "</p>"
                            + "<p>Comprueba que el servidor está activo y la URL es correcta (menú ⋮ → Cambiar servidor).</p>",
                            "text/html", "utf-8");
                }
            }
        });

        String url = prefs.getString(KEY_URL, "");
        if (url.isEmpty()) askUrl(); else open(url);
    }

    private void open(String url) {
        serverHost = Uri.parse(url).getHost() == null ? "" : Uri.parse(url).getHost();
        web.loadUrl(url);
    }

    private void askUrl() {
        final EditText in = new EditText(this);
        in.setHint("https://mi-servidor.onrender.com");
        in.setText(prefs.getString(KEY_URL, "http://192.168.50.23:8000"));
        new AlertDialog.Builder(this)
                .setTitle("URL del servidor")
                .setView(in)
                .setCancelable(!prefs.getString(KEY_URL, "").isEmpty())
                .setPositiveButton("Guardar", (d, w) -> {
                    String u = in.getText().toString().trim();
                    if (u.isEmpty()) return;
                    if (!u.startsWith("http")) u = "https://" + u;
                    prefs.edit().putString(KEY_URL, u).apply();
                    open(u);
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    @Override
    public boolean onCreateOptionsMenu(Menu m) {
        m.add(0, 1, 0, "Recargar");
        m.add(0, 2, 1, "Cambiar servidor");
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem i) {
        if (i.getItemId() == 1) {
            String u = prefs.getString(KEY_URL, "");
            if (u.isEmpty()) Toast.makeText(this, "Sin servidor", Toast.LENGTH_SHORT).show(); else open(u);
        } else if (i.getItemId() == 2) askUrl();
        return true;
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }
}
