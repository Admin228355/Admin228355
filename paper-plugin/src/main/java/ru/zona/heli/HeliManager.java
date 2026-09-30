package ru.zona.heli;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Entity;
import org.bukkit.inventory.ItemStack;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.logging.Level;

/** Хранит все вертолёты, тикает их и сохраняет в helicopters.yml. */
public final class HeliManager {

    private final HeliPlugin plugin;
    private final Map<UUID, Helicopter> helis = new LinkedHashMap<>();
    private final Map<UUID, Helicopter> byEntity = new HashMap<>();
    private final File file;

    public HeliManager(HeliPlugin plugin) {
        this.plugin = plugin;
        this.file = new File(plugin.getDataFolder(), "helicopters.yml");
    }

    public Collection<Helicopter> all() {
        return helis.values();
    }

    public Helicopter spawn(Location at) {
        Helicopter h = new Helicopter(plugin, UUID.randomUUID(), at.getWorld(), at.getX(), at.getY(), at.getZ(), at.getYaw());
        helis.put(h.id, h);
        save();
        return h;
    }

    public void remove(Helicopter h) {
        helis.remove(h.id);
        byEntity.values().removeIf(x -> x == h);
        save();
    }

    public void index(Entity e, Helicopter h) {
        byEntity.put(e.getUniqueId(), h);
    }

    public void unindex(Entity e) {
        byEntity.remove(e.getUniqueId());
    }

    public Helicopter byEntity(Entity e) {
        return e == null ? null : byEntity.get(e.getUniqueId());
    }

    public Helicopter nearest(Location l, double maxDist) {
        Helicopter best = null;
        double bd = maxDist * maxDist;
        for (Helicopter h : helis.values()) {
            if (h.world != l.getWorld()) continue;
            double d = h.pos.distanceSquared(l.getX(), l.getY(), l.getZ());
            if (d < bd) {
                bd = d;
                best = h;
            }
        }
        return best;
    }

    public void tick() {
        for (Helicopter h : new ArrayList<>(helis.values())) {
            try {
                h.tick();
            } catch (Exception ex) {
                plugin.getLogger().log(Level.WARNING, "Ошибка тика вертолёта " + h.id, ex);
            }
        }
    }

    public void shutdown() {
        for (Helicopter h : helis.values()) {
            for (var p : h.occupants()) p.leaveVehicle();
            h.clearShell();
            h.despawnEntities();
        }
    }

    // ------------------------------------------------------------ persistence

    public void save() {
        YamlConfiguration y = new YamlConfiguration();
        for (Helicopter h : helis.values()) {
            ConfigurationSection s = y.createSection("helicopters." + h.id);
            s.set("world", h.world.getName());
            s.set("x", h.pos.x);
            s.set("y", h.pos.y);
            s.set("z", h.pos.z);
            s.set("yaw", h.yaw);
            s.set("health", h.health);
            s.set("side-door", h.sideDoorOpen);
            s.set("rear-doors", h.rearOpen);
            s.set("cockpit-door", h.cockpitOpen);
            ItemStack[] items = h.getInventory().getContents();
            for (int i = 0; i < items.length; i++) {
                if (items[i] != null && !items[i].getType().isAir()) s.set("storage." + i, items[i]);
            }
            List<String> shell = new ArrayList<>();
            h.shell.forEach(k -> shell.add(k.toString()));
            s.set("shell", shell);
        }
        try {
            plugin.getDataFolder().mkdirs();
            y.save(file);
        } catch (IOException e) {
            plugin.getLogger().log(Level.WARNING, "Не удалось сохранить helicopters.yml", e);
        }
    }

    public void load() {
        if (!file.exists()) return;
        YamlConfiguration y = YamlConfiguration.loadConfiguration(file);
        ConfigurationSection root = y.getConfigurationSection("helicopters");
        if (root == null) return;
        for (String key : root.getKeys(false)) {
            ConfigurationSection s = root.getConfigurationSection(key);
            if (s == null) continue;
            World w = Bukkit.getWorld(s.getString("world", "world"));
            if (w == null) {
                plugin.getLogger().warning("Мир для вертолёта " + key + " не найден, пропускаю");
                continue;
            }
            Helicopter h = new Helicopter(plugin, UUID.fromString(key), w, s.getDouble("x"), s.getDouble("y"),
                    s.getDouble("z"), (float) s.getDouble("yaw"));
            h.health = s.getDouble("health", h.health);
            h.sideDoorOpen = s.getBoolean("side-door");
            h.rearOpen = s.getBoolean("rear-doors");
            h.cockpitOpen = s.getBoolean("cockpit-door");
            ConfigurationSection st = s.getConfigurationSection("storage");
            if (st != null) {
                for (String slot : st.getKeys(false)) {
                    ItemStack it = st.getItemStack(slot);
                    int i = Integer.parseInt(slot);
                    if (it != null && i >= 0 && i < h.getInventory().getSize()) h.getInventory().setItem(i, it);
                }
            }
            // барьеры, оставшиеся после падения сервера, считаем своими, чтобы потом убрать
            for (String k : s.getStringList("shell")) {
                Helicopter.BlockKey bk = Helicopter.BlockKey.parse(k);
                Block b = w.getBlockAt(bk.x(), bk.y(), bk.z());
                if (b.getType() == Material.BARRIER) h.shell.add(bk);
            }
            helis.put(h.id, h);
        }
        plugin.getLogger().info("Загружено вертолётов: " + helis.size());
    }
}
