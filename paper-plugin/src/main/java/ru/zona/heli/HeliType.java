package ru.zona.heli;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.joml.Vector3f;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Тип вертолёта (Ми-8, Black Hawk...). Описание генерируется из Blockbench-модели
 * скриптом blockbench/&lt;тип&gt;/generate.py и лежит в jar: types/&lt;id&gt;.yml.
 * Все точки — в единицах Blockbench (нос смотрит на -Z, y = 0 — земля), pivot частей — в блоках.
 */
public final class HeliType {

    /** Часть модели = один ItemDisplay. anim: none | spin | slide | hinge. */
    public record Part(String key, Vector3f pivot, String anim, char axis, float speed, String door,
                       Vector3f out, Vector3f slide, float angle) {}

    public record Door(String id, String name, int ticks, String openSound, String closeSound) {}

    public record Seat(String name, Vector3f pos, boolean pilot) {}

    public enum Action { SEAT, DOOR, STORAGE }

    public record Hotspot(Action action, String door, int seat, Vector3f pos, float width, float height) {}

    /** Ячейки барьеров: прямоугольник x/z (единицы модели), уровни блоков над землёй; door — проём. */
    public record ShellBox(float x0, float x1, float z0, float z1, int l0, int l1, String door) {}

    public final String id;
    public String name;
    public double blocksPerUnit;
    public float displayScale;
    public Vector3f tiltCenter;
    public Vector3f hub;
    public float rotorRadius;
    public String storageTitle;
    public int storageSize;
    public Vector3f exitInside, exitOutside;
    public Flight flight;
    public final List<Part> parts = new ArrayList<>();
    public final Map<String, Door> doors = new LinkedHashMap<>();
    public final List<Seat> seats = new ArrayList<>();
    public final List<Hotspot> hotspots = new ArrayList<>();
    public final List<Vector3f> collision = new ArrayList<>();
    public final List<Vector3f> rotorTips = new ArrayList<>();
    public final List<ShellBox> shell = new ArrayList<>();

    private HeliType(String id) {
        this.id = id;
    }

    public static List<String> index(HeliPlugin plugin) {
        YamlConfiguration y = read(plugin, "types/index.yml");
        List<String> out = new ArrayList<>();
        for (Object o : y.getList("types", List.of())) out.add(String.valueOf(o));
        return out;
    }

    private static YamlConfiguration read(HeliPlugin plugin, String path) {
        try (InputStream in = plugin.getResource(path)) {
            if (in == null) throw new IllegalStateException(path + " не найден в jar");
            return YamlConfiguration.loadConfiguration(new InputStreamReader(in, StandardCharsets.UTF_8));
        } catch (java.io.IOException e) {
            throw new IllegalStateException("Не удалось прочитать " + path, e);
        }
    }

    public static HeliType load(HeliPlugin plugin, String id, Settings settings) {
        YamlConfiguration y = read(plugin, "types/" + id + ".yml");
        HeliType t = new HeliType(id);
        t.name = y.getString("name", id);
        t.blocksPerUnit = y.getDouble("blocks-per-unit", 0.125);
        t.displayScale = (float) y.getDouble("display-scale", 8.0);
        t.tiltCenter = vec(y.getList("tilt-center"));
        t.hub = vec(y.getList("hub"));
        t.rotorRadius = (float) y.getDouble("rotor-radius", 60);
        t.storageTitle = y.getString("storage-title", "Склад");
        t.storageSize = Math.max(9, Math.min(54, y.getInt("storage-size", 54) / 9 * 9));
        t.exitInside = vec(y.getList("exit-inside"));
        t.exitOutside = vec(y.getList("exit-outside"));
        ConfigurationSection fl = y.getConfigurationSection("flight");
        t.flight = settings.flight.with(fl == null ? Map.of() : fl.getValues(false));
        // пользовательские переопределения из config.yml: types.<id>.flight
        ConfigurationSection user = plugin.getConfig().getConfigurationSection("types." + id + ".flight");
        if (user != null) t.flight = t.flight.with(user.getValues(false));

        for (Map<?, ?> m : y.getMapList("parts")) {
            String axis = str(m, "axis", "y");
            t.parts.add(new Part(str(m, "key", "?"), vec(m.get("pivot")), str(m, "anim", "none"), axis.charAt(0),
                    num(m, "speed", 0), str(m, "door", null), vec(m.get("out")), vec(m.get("slide")), num(m, "angle", 0)));
        }
        for (Map<?, ?> m : y.getMapList("doors")) {
            Door d = new Door(str(m, "id", "door"), str(m, "name", "Дверь"), (int) num(m, "ticks", 20),
                    str(m, "open-sound", "minecraft:block.iron_door.open"), str(m, "close-sound", "minecraft:block.iron_door.close"));
            t.doors.put(d.id(), d);
        }
        for (Map<?, ?> m : y.getMapList("seats")) {
            t.seats.add(new Seat(str(m, "name", "Место"), vec(m.get("pos")), Boolean.TRUE.equals(m.get("pilot"))));
        }
        for (int i = 0; i < t.seats.size(); i++) {
            Vector3f p = new Vector3f(t.seats.get(i).pos()).sub(0, 3.5f, 0);
            t.hotspots.add(new Hotspot(Action.SEAT, null, i, p, 0.8f, 0.9f));
        }
        for (Map<?, ?> m : y.getMapList("hotspots")) {
            t.hotspots.add(new Hotspot(Action.valueOf(str(m, "action", "DOOR").toUpperCase()), str(m, "door", null), -1,
                    vec(m.get("pos")), num(m, "width", 1), num(m, "height", 1)));
        }
        for (Object o : y.getList("collision", List.of())) t.collision.add(vec(o));
        for (Map<?, ?> m : y.getMapList("shell")) {
            List<?> x = (List<?>) m.get("x"), z = (List<?>) m.get("z"), l = (List<?>) m.get("levels");
            t.shell.add(new ShellBox(f(x.get(0)), f(x.get(1)), f(z.get(0)), f(z.get(1)),
                    (int) f(l.get(0)), (int) f(l.get(1)), str(m, "door", null)));
        }
        for (int i = 0; i < 12; i++) {
            double a = Math.PI * 2 * i / 12;
            t.rotorTips.add(new Vector3f((float) (t.hub.x + Math.cos(a) * t.rotorRadius), t.hub.y,
                    (float) (t.hub.z + Math.sin(a) * t.rotorRadius)));
        }
        return t;
    }

    /** Единицы модели -> блоки. */
    public Vector3f toBlocks(Vector3f units) {
        return new Vector3f(units).mul((float) blocksPerUnit);
    }

    public Seat pilotSeat() {
        return seats.isEmpty() ? null : seats.get(0);
    }

    private static Vector3f vec(Object o) {
        if (o instanceof List<?> l && l.size() >= 3) return new Vector3f(f(l.get(0)), f(l.get(1)), f(l.get(2)));
        return new Vector3f();
    }

    private static float f(Object o) {
        return o instanceof Number n ? n.floatValue() : Float.parseFloat(String.valueOf(o));
    }

    private static float num(Map<?, ?> m, String k, float def) {
        Object o = m.get(k);
        return o instanceof Number n ? n.floatValue() : def;
    }

    private static String str(Map<?, ?> m, String k, String def) {
        Object o = m.get(k);
        return o == null ? def : String.valueOf(o);
    }
}
