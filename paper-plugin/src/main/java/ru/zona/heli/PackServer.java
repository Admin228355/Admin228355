package ru.zona.heli;

import com.sun.net.httpserver.HttpServer;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;

import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.UUID;
import java.util.logging.Level;

/** Выкладывает ресурспак из jar в папку плагина и (по желанию) раздаёт его по HTTP. */
public final class PackServer {

    private static final UUID PACK_ID = UUID.nameUUIDFromBytes("heli-pack-v2".getBytes(StandardCharsets.UTF_8));
    private final HeliPlugin plugin;
    private HttpServer server;
    private byte[] data;
    private byte[] sha1;
    private String url;

    public PackServer(HeliPlugin plugin) {
        this.plugin = plugin;
    }

    public void start() {
        try (InputStream in = plugin.getResource("heli_resourcepack.zip")) {
            if (in == null) throw new IllegalStateException("heli_resourcepack.zip не найден в jar");
            data = in.readAllBytes();
            sha1 = MessageDigest.getInstance("SHA-1").digest(data);
            File out = new File(plugin.getDataFolder(), "heli_resourcepack.zip");
            plugin.getDataFolder().mkdirs();
            Files.copy(new java.io.ByteArrayInputStream(data), out.toPath(), StandardCopyOption.REPLACE_EXISTING);
        } catch (Exception e) {
            plugin.getLogger().log(Level.SEVERE, "Не удалось подготовить ресурспак", e);
            return;
        }
        String external = plugin.getConfig().getString("resource-pack.url", "");
        if (external != null && !external.isBlank()) {
            url = external;
            return;
        }
        int port = plugin.getConfig().getInt("resource-pack.port", 8163);
        String host = plugin.getConfig().getString("resource-pack.public-host", "localhost");
        try {
            server = HttpServer.create(new InetSocketAddress(port), 0);
            server.createContext("/heli_resourcepack.zip", ex -> {
                ex.getResponseHeaders().add("Content-Type", "application/zip");
                ex.sendResponseHeaders(200, data.length);
                try (OutputStream os = ex.getResponseBody()) {
                    os.write(data);
                }
            });
            server.start();
            url = "http://" + host + ":" + port + "/heli_resourcepack.zip";
            plugin.getLogger().info("Ресурспак раздаётся по адресу " + url);
        } catch (Exception e) {
            plugin.getLogger().log(Level.WARNING, "Не удалось запустить HTTP-сервер ресурспака на порту " + port
                    + ". Укажите resource-pack.url или установите plugins/Helicopters/heli_resourcepack.zip вручную.", e);
        }
    }

    public void stop() {
        if (server != null) server.stop(0);
    }

    public void send(Player p) {
        if (url == null || !plugin.getConfig().getBoolean("resource-pack.send-on-join", true)) return;
        boolean force = plugin.getConfig().getBoolean("resource-pack.required", false);
        try {
            p.setResourcePack(PACK_ID, url, sha1, Component.text("Модели вертолётов"), force);
        } catch (NoSuchMethodError e) {
            p.setResourcePack(PACK_ID, url, sha1, "Модели вертолётов", force);
        }
    }
}
