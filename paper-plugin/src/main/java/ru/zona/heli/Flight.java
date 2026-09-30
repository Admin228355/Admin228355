package ru.zona.heli;

import java.util.Map;

/** Параметры полёта. Общие значения — из config.yml, тип вертолёта может переопределить. */
public record Flight(double health, int startupTicks, int shutdownTicks, double accel, double strafeAccel,
                     double climbAccel, double gravity, double maxSpeed, double boost, double turnRate,
                     double drag, double crashSpeed, double crashDamage) {

    public static final Flight DEFAULTS = new Flight(100, 100, 140, 0.035, 0.02, 0.03, 0.06, 1.1, 1.7, 3.5,
            0.965, 0.75, 120);

    public Flight with(Map<?, ?> m) {
        return new Flight(
                d(m, "health", health),
                (int) Math.max(1, d(m, "startup-seconds", startupTicks / 20.0) * 20),
                (int) Math.max(1, d(m, "shutdown-seconds", shutdownTicks / 20.0) * 20),
                d(m, "accel", accel),
                d(m, "strafe-accel", strafeAccel),
                d(m, "climb-accel", climbAccel),
                d(m, "gravity", gravity),
                d(m, "max-speed", maxSpeed),
                d(m, "boost-multiplier", boost),
                d(m, "turn-rate", turnRate),
                d(m, "drag", drag),
                d(m, "crash-speed", crashSpeed),
                d(m, "crash-damage", crashDamage));
    }

    private static double d(Map<?, ?> m, String key, double def) {
        Object o = m.get(key);
        return o instanceof Number n ? n.doubleValue() : def;
    }
}
