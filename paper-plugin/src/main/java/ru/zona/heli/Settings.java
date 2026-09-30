package ru.zona.heli;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;

/** Общие настройки из config.yml. */
public final class Settings {

    public final float yawOffset;
    public final double seatYOffset;
    public final float viewRange;
    public final boolean shellEnabled;
    public final boolean rotorStrike;
    public final boolean allowJumpOut;
    public final int engineOffDelay;
    public final String rotorSound;
    public final boolean downwash;
    public final String defaultType;
    public final Flight flight;

    public Settings(FileConfiguration c) {
        yawOffset = (float) c.getDouble("model.yaw-offset", 180);
        seatYOffset = c.getDouble("model.seat-y-offset", -0.35);
        viewRange = (float) c.getDouble("model.view-range", 4.0);
        shellEnabled = c.getBoolean("shell.enabled", true);
        rotorStrike = c.getBoolean("flight.rotor-strike", true);
        allowJumpOut = c.getBoolean("flight.allow-jump-out", false);
        engineOffDelay = c.getInt("flight.engine-off-delay", 100);
        rotorSound = c.getString("effects.rotor-sound", "minecraft:entity.phantom.flap");
        downwash = c.getBoolean("effects.downwash", true);
        defaultType = c.getString("default-type", "blackhawk");
        ConfigurationSection f = c.getConfigurationSection("flight");
        flight = Flight.DEFAULTS.with(f == null ? java.util.Map.of() : f.getValues(false));
    }
}
