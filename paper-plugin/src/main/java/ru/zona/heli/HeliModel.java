package ru.zona.heli;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.configuration.file.YamlConfiguration;
import org.joml.Vector3f;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Описание модели Ми-8: части, сиденья, кнопки, точки коллизии и параметры полёта. */
public final class HeliModel {

    public record Part(String key, Vector3f pivot) {}

    public record Seat(String name, Vector3f pos, boolean pilot) {}

    public enum Action { SEAT, SIDE_DOOR, REAR_DOORS, COCKPIT_DOOR, STORAGE }

    public record Hotspot(Action action, int seat, Vector3f pos, float width, float height) {}

    public final Map<String, Part> parts = new LinkedHashMap<>();
    public final List<Seat> seats = new ArrayList<>();
    public final List<Hotspot> hotspots = new ArrayList<>();
    /** Точки корпуса для столкновений с блоками (в единицах модели). */
    public final List<Vector3f> collision = new ArrayList<>();
    /** Концы лопастей для удара о блоки. */
    public final List<Vector3f> rotorTips = new ArrayList<>();

    public double blocksPerUnit = 0.125;
    public float displayScale = 8f;
    public float yawOffset = 180f;
    public double seatYOffset = -0.35;
    public float viewRange = 4f;
    /** Центр наклона корпуса (блоки). */
    public final Vector3f tiltCenter = new Vector3f(0f, 2.2f, 0f);
    public static final float HUB_Y = 33.4f;

    public boolean shellEnabled;
    public double health, accel, strafeAccel, climbAccel, gravity, maxSpeed, boost, turnRate, drag;
    public double crashSpeed, crashDamage;
    public int startupTicks, shutdownTicks, engineOffDelay;
    public boolean rotorStrike, allowJumpOut, downwash;
    public String rotorSound;

    public static HeliModel load(HeliPlugin plugin) {
        HeliModel m = new HeliModel();
        try (InputStream in = plugin.getResource("mi8_parts.yml")) {
            if (in == null) throw new IllegalStateException("mi8_parts.yml не найден в jar");
            YamlConfiguration y = YamlConfiguration.loadConfiguration(new InputStreamReader(in, StandardCharsets.UTF_8));
            m.blocksPerUnit = y.getDouble("blocks-per-unit", 0.125);
            m.displayScale = (float) y.getDouble("display-scale", 8.0);
            ConfigurationSection ps = y.getConfigurationSection("parts");
            if (ps != null) {
                for (String key : ps.getKeys(false)) {
                    List<Double> p = ps.getDoubleList(key + ".pivot");
                    m.parts.put(key, new Part(key, new Vector3f(p.get(0).floatValue(), p.get(1).floatValue(), p.get(2).floatValue())));
                }
            }
        } catch (Exception e) {
            throw new IllegalStateException("Не удалось прочитать mi8_parts.yml", e);
        }

        FileConfiguration c = plugin.getConfig();
        m.yawOffset = (float) c.getDouble("model.yaw-offset", 180);
        m.seatYOffset = c.getDouble("model.seat-y-offset", -0.35);
        m.viewRange = (float) c.getDouble("model.view-range", 4.0);

        for (Map<?, ?> s : c.getMapList("seats")) {
            m.seats.add(new Seat(String.valueOf(s.get("name")), vec(s.get("pos")), Boolean.TRUE.equals(s.get("pilot"))));
        }
        if (m.seats.isEmpty() || !m.seats.get(0).pilot()) {
            m.seats.add(0, new Seat("Пилот", new Vector3f(-4.6f, 11.2f, -32.5f), true));
        }
        for (int i = 0; i < m.seats.size(); i++) {
            Vector3f p = new Vector3f(m.seats.get(i).pos()).sub(0, 3.5f, 0);
            m.hotspots.add(new Hotspot(Action.SEAT, i, p, 0.8f, 0.9f));
        }
        for (Map<?, ?> h : c.getMapList("hotspots")) {
            Action a = Action.valueOf(String.valueOf(h.get("action")).toUpperCase());
            float w = h.get("width") instanceof Number n ? n.floatValue() : 1f;
            float hh = h.get("height") instanceof Number n ? n.floatValue() : 1f;
            m.hotspots.add(new Hotspot(a, -1, vec(h.get("pos")), w, hh));
        }

        m.shellEnabled = c.getBoolean("shell.enabled", true);
        m.health = c.getDouble("flight.health", 100);
        m.startupTicks = (int) Math.max(1, c.getDouble("flight.startup-seconds", 5) * 20);
        m.shutdownTicks = (int) Math.max(1, c.getDouble("flight.shutdown-seconds", 7) * 20);
        m.accel = c.getDouble("flight.accel", 0.035);
        m.strafeAccel = c.getDouble("flight.strafe-accel", 0.02);
        m.climbAccel = c.getDouble("flight.climb-accel", 0.03);
        m.gravity = c.getDouble("flight.gravity", 0.06);
        m.maxSpeed = c.getDouble("flight.max-speed", 1.1);
        m.boost = c.getDouble("flight.boost-multiplier", 1.7);
        m.turnRate = c.getDouble("flight.turn-rate", 3.5);
        m.drag = c.getDouble("flight.drag", 0.965);
        m.crashSpeed = c.getDouble("flight.crash-speed", 0.75);
        m.crashDamage = c.getDouble("flight.crash-damage", 120);
        m.rotorStrike = c.getBoolean("flight.rotor-strike", true);
        m.allowJumpOut = c.getBoolean("flight.allow-jump-out", false);
        m.engineOffDelay = c.getInt("flight.engine-off-delay", 100);
        m.rotorSound = c.getString("effects.rotor-sound", "minecraft:entity.phantom.flap");
        m.downwash = c.getBoolean("effects.downwash", true);

        m.initGeometry();
        return m;
    }

    /** Точки столкновений и концы лопастей (в единицах модели). */
    public void initGeometry() {
        collision.clear();
        rotorTips.clear();
        // Точки столкновений: колёса, днище, борта, крыша, нос, балка, киль
        collision.add(new Vector3f(-17.6f, 0.3f, 1.5f));
        collision.add(new Vector3f(17.6f, 0.3f, 1.5f));
        collision.add(new Vector3f(0f, 0.3f, -40.2f));
        collision.add(new Vector3f(0f, 15.8f, 93f));
        for (float z = -44; z <= 20; z += 8) {
            collision.add(new Vector3f(-11f, 9f, z));
            collision.add(new Vector3f(11f, 9f, z));
            collision.add(new Vector3f(-10.5f, 23f, z));
            collision.add(new Vector3f(10.5f, 23f, z));
            collision.add(new Vector3f(0f, 5.5f, z));
            collision.add(new Vector3f(0f, 29f, z));
        }
        collision.add(new Vector3f(0f, 11f, -48f));
        collision.add(new Vector3f(0f, 20f, -44f));
        for (float z = 28; z <= 104; z += 8) collision.add(new Vector3f(0f, 23f, z));
        collision.add(new Vector3f(0f, 38f, 108f));
        collision.add(new Vector3f(0f, HUB_Y + 1, -13f));
        for (int i = 0; i < 12; i++) {
            double a = Math.PI * 2 * i / 12;
            rotorTips.add(new Vector3f((float) (Math.cos(a) * 84), HUB_Y, (float) (-13 + Math.sin(a) * 84)));
        }
    }

    private static Vector3f vec(Object o) {
        if (o instanceof List<?> l && l.size() >= 3) {
            return new Vector3f(num(l.get(0)), num(l.get(1)), num(l.get(2)));
        }
        return new Vector3f();
    }

    private static float num(Object o) {
        return o instanceof Number n ? n.floatValue() : Float.parseFloat(String.valueOf(o));
    }

    /** Единицы модели -> блоки. */
    public Vector3f toBlocks(Vector3f units) {
        return new Vector3f(units).mul((float) blocksPerUnit);
    }
}
