package ru.zona.heli;

import org.bukkit.Bukkit;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.command.PluginCommand;
import org.bukkit.entity.Entity;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;

/** Плагин вертолётов (Ми-8, Black Hawk) для Paper 26.1.2. */
public final class HeliPlugin extends JavaPlugin {

    private NamespacedKey tagKey;
    private Settings settings;
    private final Map<String, HeliType> types = new LinkedHashMap<>();
    private HeliManager manager;
    private PackServer packServer;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        tagKey = new NamespacedKey(this, "heli");
        settings = new Settings(getConfig());
        for (String id : HeliType.index(this)) {
            try {
                types.put(id, HeliType.load(this, id, settings));
            } catch (Exception e) {
                getLogger().log(Level.SEVERE, "Не удалось загрузить тип вертолёта " + id, e);
            }
        }

        // на всякий случай убрать сущности вертолётов, оставшиеся от прошлого запуска
        for (World w : Bukkit.getWorlds()) {
            for (Entity e : w.getEntities()) {
                if (e.getPersistentDataContainer().has(tagKey, PersistentDataType.STRING)) e.remove();
            }
        }

        manager = new HeliManager(this);
        manager.load();
        packServer = new PackServer(this);
        packServer.start();

        getServer().getPluginManager().registerEvents(new HeliListener(this), this);
        HeliCommand cmd = new HeliCommand(this);
        PluginCommand pc = getCommand("heli");
        if (pc != null) {
            pc.setExecutor(cmd);
            pc.setTabCompleter(cmd);
        }
        Bukkit.getScheduler().runTaskTimer(this, manager::tick, 1L, 1L);
        Bukkit.getScheduler().runTaskTimer(this, manager::save, 20L * 60, 20L * 60);
        getLogger().info("Вертолёты: " + String.join(", ", types.keySet()));
    }

    @Override
    public void onDisable() {
        if (manager != null) {
            manager.save();
            manager.shutdown();
        }
        if (packServer != null) packServer.stop();
    }

    public NamespacedKey tagKey() {
        return tagKey;
    }

    public Settings settings() {
        return settings;
    }

    public HeliType type(String id) {
        return id == null ? null : types.get(id.toLowerCase());
    }

    public List<String> typeIds() {
        return new ArrayList<>(types.keySet());
    }

    public HeliManager manager() {
        return manager;
    }

    public PackServer packServer() {
        return packServer;
    }
}
