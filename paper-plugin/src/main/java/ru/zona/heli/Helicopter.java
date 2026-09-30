package ru.zona.heli;

import io.papermc.paper.entity.TeleportFlag;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.Input;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Particle;
import org.bukkit.SoundCategory;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.HumanEntity;
import org.bukkit.entity.Interaction;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;
import org.joml.Matrix4f;
import org.joml.Vector3d;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** Один вертолёт в мире: физика, анимация частей, сиденья, двери, склад и коллизия. */
public final class Helicopter implements InventoryHolder {

    public record BlockKey(int x, int y, int z) {
        static BlockKey of(Block b) { return new BlockKey(b.getX(), b.getY(), b.getZ()); }
        @Override public String toString() { return x + "," + y + "," + z; }
        static BlockKey parse(String s) {
            String[] p = s.split(",");
            return new BlockKey(Integer.parseInt(p[0]), Integer.parseInt(p[1]), Integer.parseInt(p[2]));
        }
    }

    private final HeliPlugin plugin;
    private final HeliModel model;
    public final UUID id;
    public World world;
    public final Vector3d pos = new Vector3d();
    public final Vector3d vel = new Vector3d();
    public float yaw;               // куда смотрит нос (как yaw игрока)
    private float pitch, roll, yawRate;
    public double rotor;            // 0..1 обороты винта
    public boolean engineOn;
    public double health;
    public boolean sideDoorOpen, rearOpen, cockpitOpen;
    private double sideT, rearT, cockpitT;
    private double rotorAngle, tailAngle;
    public boolean landed = true;
    private int noPilotTicks;
    private long ticks;
    public boolean destroyed;

    private final Inventory storage;
    private final Map<String, ItemDisplay> parts = new LinkedHashMap<>();
    private final List<ItemDisplay> seats = new ArrayList<>();
    private final Map<UUID, HeliModel.Hotspot> hotspotByEntity = new HashMap<>();
    private final List<Interaction> hotspots = new ArrayList<>();
    public final Set<BlockKey> shell = new HashSet<>();
    private boolean shellDirty = true;
    private boolean spawned;

    public Helicopter(HeliPlugin plugin, UUID id, World world, double x, double y, double z, float yaw) {
        this.plugin = plugin;
        this.model = plugin.model();
        this.id = id;
        this.world = world;
        this.pos.set(x, y, z);
        this.yaw = yaw;
        this.health = model.health;
        this.storage = Bukkit.createInventory(this, 54, Component.text("Склад Ми-8"));
    }

    @Override
    public Inventory getInventory() {
        return storage;
    }

    // ------------------------------------------------------------------ math

    /** Матрица корпуса: локальные блоки -> смещение от pos (рыскание + тангаж + крен). */
    private Matrix4f bodyMatrix() {
        Vector3f c = model.tiltCenter;
        return new Matrix4f()
                .rotateY((float) Math.toRadians(180.0 - yaw))
                .translate(c)
                .rotateX((float) Math.toRadians(-pitch))
                .rotateZ((float) Math.toRadians(-roll))
                .translate(-c.x, -c.y, -c.z);
    }

    /** Точка модели (единицы Blockbench) -> координаты мира. */
    public Location worldPoint(Vector3f units) {
        Vector3f v = bodyMatrix().transformPosition(model.toBlocks(units));
        return new Location(world, pos.x + v.x, pos.y + v.y, pos.z + v.z);
    }

    private double[] yawRotate(double lx, double lz) {
        double t = Math.toRadians(180.0 - yaw);
        return new double[]{Math.cos(t) * lx + Math.sin(t) * lz, -Math.sin(t) * lx + Math.cos(t) * lz};
    }

    private double[] yawInverse(double wx, double wz) {
        double t = Math.toRadians(180.0 - yaw);
        return new double[]{Math.cos(t) * wx - Math.sin(t) * wz, Math.sin(t) * wx + Math.cos(t) * wz};
    }

    private static double ease(double t) {
        return t * t * (3 - 2 * t);
    }

    // -------------------------------------------------------------- entities

    public boolean isSpawned() {
        return spawned;
    }

    private Location base() {
        return new Location(world, pos.x, pos.y, pos.z, 0f, 0f);
    }

    public void spawnEntities() {
        despawnEntities();
        NamespacedKey tag = plugin.tagKey();
        Location base = base();
        for (HeliModel.Part part : model.parts.values()) {
            ItemDisplay d = world.spawn(base, ItemDisplay.class, e -> {
                ItemStack item = new ItemStack(Material.STICK);
                ItemMeta meta = item.getItemMeta();
                meta.setItemModel(new NamespacedKey("heli", part.key()));
                item.setItemMeta(meta);
                e.setItemStack(item);
                e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.NONE);
                e.setPersistent(false);
                e.setViewRange(model.viewRange);
                e.setDisplayWidth(32f);
                e.setDisplayHeight(12f);
                e.setShadowRadius(0f);
                e.setTeleportDuration(2);
                e.setInterpolationDuration(2);
                e.getPersistentDataContainer().set(tag, PersistentDataType.STRING, id.toString());
            });
            parts.put(part.key(), d);
        }
        for (HeliModel.Seat seat : model.seats) {
            ItemDisplay s = world.spawn(worldPoint(seat.pos()), ItemDisplay.class, e -> {
                e.setPersistent(false);
                e.setTeleportDuration(2);
                e.getPersistentDataContainer().set(tag, PersistentDataType.STRING, id.toString());
            });
            seats.add(s);
            plugin.manager().index(s, this);
        }
        for (HeliModel.Hotspot h : model.hotspots) {
            Interaction in = world.spawn(hotspotLocation(h), Interaction.class, e -> {
                e.setInteractionWidth(h.width());
                e.setInteractionHeight(h.height());
                e.setResponsive(true);
                e.setPersistent(false);
                e.getPersistentDataContainer().set(tag, PersistentDataType.STRING, id.toString());
            });
            hotspots.add(in);
            hotspotByEntity.put(in.getUniqueId(), h);
            plugin.manager().index(in, this);
        }
        spawned = true;
        updateEntities(true);
    }

    public void despawnEntities() {
        for (ItemDisplay s : seats) {
            s.eject();
            plugin.manager().unindex(s);
            s.remove();
        }
        for (Interaction in : hotspots) {
            plugin.manager().unindex(in);
            in.remove();
        }
        parts.values().forEach(Entity::remove);
        parts.clear();
        seats.clear();
        hotspots.clear();
        hotspotByEntity.clear();
        spawned = false;
    }

    private Location hotspotLocation(HeliModel.Hotspot h) {
        Location l = worldPoint(h.pos());
        l.setY(l.getY() - h.height() / 2 + 0.2);
        return l;
    }

    private boolean entitiesValid() {
        for (ItemDisplay d : parts.values()) if (!d.isValid()) return false;
        for (ItemDisplay s : seats) if (!s.isValid()) return false;
        for (Interaction i : hotspots) if (!i.isValid()) return false;
        return true;
    }

    private void updateEntities(boolean force) {
        Matrix4f body = bodyMatrix();
        Location base = base();
        float s = model.displayScale;
        for (HeliModel.Part part : model.parts.values()) {
            ItemDisplay d = parts.get(part.key());
            if (d == null) continue;
            Vector3f pv = new Vector3f(part.pivot());          // pivot в mi8_parts.yml уже в блоках
            Matrix4f m = new Matrix4f(body).translate(pv);
            switch (part.key()) {
                case "mi8_main_rotor" -> m.rotateY((float) Math.toRadians(rotorAngle));
                case "mi8_tail_rotor" -> m.rotateX((float) Math.toRadians(tailAngle));
                case "mi8_side_door" -> {
                    double out = Math.min(1, sideT / 0.25), slide = Math.max(0, (sideT - 0.25) / 0.75);
                    m.translate((float) (-1.4 * ease(out) * model.blocksPerUnit), 0f,
                            (float) (9.4 * ease(slide) * model.blocksPerUnit));
                }
                case "mi8_rear_door_l" -> m.rotateY((float) Math.toRadians(-105 * ease(rearT)));
                case "mi8_rear_door_r" -> m.rotateY((float) Math.toRadians(105 * ease(rearT)));
                case "mi8_cockpit_door" -> m.rotateY((float) Math.toRadians(95 * ease(cockpitT)));
                default -> { }
            }
            m.scale(s).rotateY((float) Math.toRadians(model.yawOffset));
            if (force || moving()) d.teleport(base);
            d.setInterpolationDelay(0);
            d.setTransformationMatrix(m);
        }
        for (int i = 0; i < seats.size(); i++) {
            Location l = worldPoint(model.seats.get(i).pos());
            l.setY(l.getY() + model.seatYOffset);
            l.setYaw(yaw);
            seats.get(i).teleport(l, TeleportFlag.EntityState.RETAIN_PASSENGERS);
        }
        for (Interaction in : hotspots) {
            HeliModel.Hotspot h = hotspotByEntity.get(in.getUniqueId());
            if (h != null) in.teleport(hotspotLocation(h));
        }
    }

    private boolean moving() {
        return !landed || vel.lengthSquared() > 1e-6 || Math.abs(pitch) > 0.05 || Math.abs(roll) > 0.05;
    }

    // ----------------------------------------------------------------- seats

    public Player pilot() {
        if (seats.isEmpty()) return null;
        for (Entity e : seats.get(0).getPassengers()) if (e instanceof Player p) return p;
        return null;
    }

    public int seatIndex(Entity seatEntity) {
        return seats.indexOf(seatEntity);
    }

    public HeliModel.Hotspot hotspot(Entity e) {
        return hotspotByEntity.get(e.getUniqueId());
    }

    public void sit(Player p, int index) {
        if (index < 0 || index >= seats.size()) return;
        HeliModel.Seat seat = model.seats.get(index);
        if (seat.pilot() && !p.hasPermission("heli.pilot")) {
            p.sendActionBar(Component.text("Нет прав пилота", NamedTextColor.RED));
            return;
        }
        ItemDisplay s = seats.get(index);
        if (!s.getPassengers().isEmpty()) {
            p.sendActionBar(Component.text("Место занято", NamedTextColor.RED));
            return;
        }
        if (p.isInsideVehicle()) p.leaveVehicle();
        s.addPassenger(p);
        if (seat.pilot()) {
            p.sendMessage(Component.text("Вы пилот. Пробел — запуск/вверх, Shift — вниз (на земле — выйти), "
                    + "W/S — вперёд/назад, A/D — вбок, Ctrl — форсаж, поворот — мышью.", NamedTextColor.GREEN));
        } else {
            p.sendActionBar(Component.text("Место: " + seat.name(), NamedTextColor.GREEN));
        }
    }

    /** Куда высадить игрока после выхода. */
    public Location exitPoint() {
        Vector3f p = shell.isEmpty() ? new Vector3f(-22f, 1f, -19.5f) : new Vector3f(-5f, 9f, -19.5f);
        if (!shell.isEmpty() && !sideDoorOpen) p = new Vector3f(0f, 9f, -12f);
        Location l = worldPoint(p);
        l.setYaw(yaw);
        return l;
    }

    public List<Player> occupants() {
        List<Player> out = new ArrayList<>();
        for (ItemDisplay s : seats) for (Entity e : s.getPassengers()) if (e instanceof Player p) out.add(p);
        return out;
    }

    // ----------------------------------------------------------------- doors

    public void toggle(HeliModel.Action a, Player who) {
        String sound;
        switch (a) {
            case SIDE_DOOR -> { sideDoorOpen = !sideDoorOpen; sound = sideDoorOpen ? "minecraft:block.iron_trapdoor.open" : "minecraft:block.iron_trapdoor.close"; }
            case REAR_DOORS -> { rearOpen = !rearOpen; sound = rearOpen ? "minecraft:block.iron_door.open" : "minecraft:block.iron_door.close"; }
            case COCKPIT_DOOR -> { cockpitOpen = !cockpitOpen; sound = cockpitOpen ? "minecraft:block.wooden_door.open" : "minecraft:block.wooden_door.close"; }
            case STORAGE -> {
                who.openInventory(storage);
                world.playSound(who.getLocation(), "minecraft:block.chest.open", SoundCategory.BLOCKS, 0.8f, 0.9f);
                return;
            }
            default -> { return; }
        }
        world.playSound(who.getLocation(), sound, SoundCategory.BLOCKS, 1f, 0.8f);
        shellDirty = true;
    }

    // ------------------------------------------------------------ main tick

    public void tick() {
        if (destroyed) return;
        ticks++;
        int cx = (int) Math.floor(pos.x) >> 4, cz = (int) Math.floor(pos.z) >> 4;
        if (!world.isChunkLoaded(cx, cz)) {
            if (spawned) despawnEntities();
            return;
        }
        if (!spawned || (ticks % 20 == 0 && !entitiesValid())) spawnEntities();

        Player pilot = pilot();
        Input in = pilot != null ? pilot.getCurrentInput() : null;

        // двигатель
        if (pilot != null) {
            noPilotTicks = 0;
            if (!engineOn && in.isJump()) {
                engineOn = true;
                pilot.sendActionBar(Component.text("Запуск двигателей...", NamedTextColor.YELLOW));
            }
        } else if (landed && engineOn && ++noPilotTicks > model.engineOffDelay) {
            engineOn = false;
        }
        rotor = engineOn ? Math.min(1, rotor + 1.0 / model.startupTicks) : Math.max(0, rotor - 1.0 / model.shutdownTicks);

        physics(pilot, in);
        animate();
        updateShell();
        if (spawned && (moving() || rotor > 0 || animatingDoors() || ticks % 40 == 0)) updateEntities(false);
        effects(pilot);
    }

    private boolean animatingDoors() {
        return (sideT > 0 && sideT < 1) || (rearT > 0 && rearT < 1) || (cockpitT > 0 && cockpitT < 1)
                || (sideDoorOpen ? sideT < 1 : sideT > 0) || (rearOpen ? rearT < 1 : rearT > 0)
                || (cockpitOpen ? cockpitT < 1 : cockpitT > 0);
    }

    private void animate() {
        rotorAngle = (rotorAngle + rotor * 36) % 360;       // до 2 об/с
        tailAngle = (tailAngle + rotor * 100) % 360;
        sideT = approach(sideT, sideDoorOpen ? 1 : 0, 1 / 24.0);
        rearT = approach(rearT, rearOpen ? 1 : 0, 1 / 32.0);
        cockpitT = approach(cockpitT, cockpitOpen ? 1 : 0, 1 / 16.0);
    }

    private static double approach(double v, double target, double step) {
        return v < target ? Math.min(target, v + step) : Math.max(target, v - step);
    }

    // --------------------------------------------------------------- physics

    private void physics(Player pilot, Input in) {
        double lift = clamp((rotor - 0.7) / 0.3, 0, 1);
        double f = 0, s = 0, up = 0;
        boolean boost = false;
        if (in != null) {
            f = (in.isForward() ? 1 : 0) - (in.isBackward() ? 1 : 0);
            s = (in.isRight() ? 1 : 0) - (in.isLeft() ? 1 : 0);
            up = (in.isJump() ? 1 : 0) - (in.isSneak() ? 1 : 0);
            boost = in.isSprint();
        }
        if (landed && up < 0) up = 0;

        // поворот за взглядом пилота
        float before = yaw;
        if (pilot != null && rotor > 0.5) {
            float target = pilot.getLocation().getYaw();
            float diff = wrap(target - yaw);
            double rate = model.turnRate * (landed ? 0.35 : 1) * rotor;
            yaw = wrap(yaw + (float) clamp(diff, -rate, rate));
        }
        yawRate = wrap(yaw - before);

        double rad = Math.toRadians(yaw);
        double fx = -Math.sin(rad), fz = Math.cos(rad);          // вперёд
        double rx = -Math.cos(rad), rz = -Math.sin(rad);          // вправо
        double a = model.accel * lift * (boost ? model.boost : 1);
        if (!landed || up > 0) {
            vel.x += (fx * f * a) + (rx * s * model.strafeAccel * lift);
            vel.z += (fz * f * a) + (rz * s * model.strafeAccel * lift);
        }
        vel.y += up * model.climbAccel * lift - model.gravity * (1 - lift);
        if (lift >= 1 && up == 0) vel.y *= 0.8;                  // удержание высоты
        vel.x *= model.drag;
        vel.z *= model.drag;
        vel.y *= 0.93;
        double max = model.maxSpeed * (boost ? model.boost : 1);
        double h = Math.hypot(vel.x, vel.z);
        if (h > max) {
            vel.x *= max / h;
            vel.z *= max / h;
        }
        vel.y = clamp(vel.y, -1.5, 0.6);

        double impact = 0;
        double vy = vel.y;
        if (!tryMove(1, vel.y)) {
            impact = Math.max(impact, Math.abs(vy));
            vel.y = 0;
        }
        double hx = vel.x, hz = vel.z;
        if (!tryMove(0, vel.x)) { impact = Math.max(impact, Math.abs(hx)); vel.x = 0; }
        if (!tryMove(2, vel.z)) { impact = Math.max(impact, Math.abs(hz)); vel.z = 0; }

        pos.y -= 0.06;
        boolean ground = collides();
        pos.y += 0.06;
        if (ground && !landed && vy < 0) {
            world.playSound(worldPoint(new Vector3f(0, 0, 0)), "minecraft:block.anvil.land", SoundCategory.NEUTRAL, 0.4f, 0.6f);
        }
        landed = ground;
        if (landed) {
            vel.x *= 0.55;
            vel.z *= 0.55;
            if (vel.y < 0) vel.y = 0;
        }
        if (impact > model.crashSpeed) {
            damage((impact - model.crashSpeed) * model.crashDamage, null);
        }

        // визуальный наклон
        double targetPitch = landed ? 0 : f * 10 * lift + (h / Math.max(0.01, model.maxSpeed)) * 3 * Math.signum(f);
        double targetRoll = landed ? 0 : s * 9 * lift + yawRate * 2.5;
        pitch += (float) ((targetPitch - pitch) * 0.12);
        roll += (float) ((clamp(targetRoll, -20, 20) - roll) * 0.12);
    }

    private boolean tryMove(int axis, double delta) {
        if (Math.abs(delta) < 1e-7) return true;
        int steps = (int) Math.ceil(Math.abs(delta) / 0.4);
        double step = delta / steps;
        for (int i = 0; i < steps; i++) {
            double old = pos.get(axis);
            pos.setComponent(axis, old + step);
            if (collides()) {
                double lo = 0, hi = step;
                for (int k = 0; k < 6; k++) {
                    double mid = (lo + hi) / 2;
                    pos.setComponent(axis, old + mid);
                    if (collides()) hi = mid; else lo = mid;
                }
                pos.setComponent(axis, old + lo);
                return false;
            }
        }
        return true;
    }

    private boolean collides() {
        double k = model.blocksPerUnit;
        for (Vector3f p : model.collision) {
            double[] xz = yawRotate(p.x * k, p.z * k);
            if (solid(pos.x + xz[0], pos.y + p.y * k, pos.z + xz[1])) return true;
        }
        return false;
    }

    private boolean solid(double x, double y, double z) {
        Block b = world.getBlockAt((int) Math.floor(x), (int) Math.floor(y), (int) Math.floor(z));
        if (shell.contains(BlockKey.of(b))) return false;
        return b.getType().isSolid() && !b.isPassable();
    }

    private static double clamp(double v, double lo, double hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    private static float wrap(float a) {
        a %= 360;
        if (a > 180) a -= 360;
        if (a < -180) a += 360;
        return a;
    }

    // ------------------------------------------------------ collision shell

    private void updateShell() {
        boolean want = model.shellEnabled && landed && !engineOn && rotor < 0.35;
        if (!want) {
            if (!shell.isEmpty()) clearShell();
            shellDirty = true;
            return;
        }
        if (shellDirty) {
            rebuildShell();
            shellDirty = false;
        }
    }

    /** Невидимые барьеры вокруг салона: пол, борта, крыша, балка. Проёмы — там, где открыты двери. */
    private void rebuildShell() {
        Set<BlockKey> want = new HashSet<>();
        int bx = (int) Math.floor(pos.x), by = (int) Math.floor(pos.y), bz = (int) Math.floor(pos.z);
        for (int dx = -15; dx <= 15; dx++) {
            for (int dz = -15; dz <= 15; dz++) {
                double[] l = yawInverse(bx + dx + 0.5 - pos.x, bz + dz + 0.5 - pos.z);
                double mx = l[0] / model.blocksPerUnit, mz = l[1] / model.blocksPerUnit;
                for (int level = 0; level <= 3; level++) {
                    if (shellCell(mx, mz, level)) want.add(new BlockKey(bx + dx, by + level, bz + dz));
                }
            }
        }
        // убрать лишние
        for (BlockKey k : new ArrayList<>(shell)) {
            if (!want.contains(k)) {
                Block b = world.getBlockAt(k.x(), k.y(), k.z());
                if (b.getType() == Material.BARRIER) b.setType(Material.AIR, false);
                shell.remove(k);
            }
        }
        // поставить новые (только в воздух)
        for (BlockKey k : want) {
            if (shell.contains(k)) continue;
            Block b = world.getBlockAt(k.x(), k.y(), k.z());
            if (b.getType().isAir()) {
                b.setType(Material.BARRIER, false);
                shell.add(k);
            }
        }
        // игроков, оказавшихся в полу, поднять
        for (Player p : world.getPlayers()) {
            if (p.getLocation().distanceSquared(new Location(world, pos.x, pos.y, pos.z)) > 400) continue;
            if (p.isInsideVehicle()) continue;
            Block feet = p.getLocation().getBlock();
            if (shell.contains(BlockKey.of(feet))) p.teleport(p.getLocation().add(0, 1, 0));
        }
    }

    private boolean shellCell(double mx, double mz, int level) {
        double ax = Math.abs(mx);
        boolean cabin = mz >= -46 && mz <= 21;
        switch (level) {
            case 0:
                return ax <= 17 && cabin;
            case 1:
            case 2:
                if (cabin && ax > 8.8 && ax <= 17) {
                    return !(sideDoorOpen && mx < 0 && mz >= -25 && mz <= -14);
                }
                if (mz < -46 && mz >= -54 && ax <= 17) return true;                  // нос
                if (mz > 21 && mz <= 30 && ax <= 17) return !rearOpen;              // створки
                return level == 2 && mz > 30 && mz <= 104 && ax <= 5;               // балка
            case 3:
                if (ax <= 17 && mz >= -46 && mz <= 30) return true;                 // крыша
                return mz > 30 && mz <= 104 && ax <= 5;
            default:
                return false;
        }
    }

    public void clearShell() {
        for (BlockKey k : shell) {
            Block b = world.getBlockAt(k.x(), k.y(), k.z());
            if (b.getType() == Material.BARRIER) b.setType(Material.AIR, false);
        }
        shell.clear();
    }

    // --------------------------------------------------------------- effects

    private void effects(Player pilot) {
        if (rotor > 0.05 && ticks % 4 == 0) {
            world.playSound(worldPoint(new Vector3f(0, HeliModel.HUB_Y, -13)), model.rotorSound, SoundCategory.NEUTRAL,
                    (float) (0.6 + rotor * 1.6), (float) (0.4 + rotor * 0.35));
        }
        if (model.downwash && rotor > 0.6 && ticks % 2 == 0) {
            int ground = groundBelow(12);
            if (ground != Integer.MIN_VALUE) {
                double strength = 1 - (pos.y - ground) / 13.0;
                for (int i = 0; i < 6 * strength * rotor; i++) {
                    double a = Math.random() * Math.PI * 2, r = 3 + Math.random() * 6;
                    world.spawnParticle(Particle.CLOUD, pos.x + Math.cos(a) * r, ground + 1.1, pos.z + Math.sin(a) * r,
                            0, Math.cos(a) * 0.35, 0.02, Math.sin(a) * 0.35, 1.0);
                }
            }
        }
        if (health < model.health * 0.4 && ticks % 3 == 0) {
            Location l = worldPoint(new Vector3f(0, 30, -13));
            world.spawnParticle(Particle.LARGE_SMOKE, l, 2, 0.4, 0.2, 0.4, 0.01);
        }
        if (model.rotorStrike && rotor > 0.5 && ticks % 5 == 0) {
            int hits = 0;
            double k = model.blocksPerUnit;
            for (Vector3f t : model.rotorTips) {
                double[] xz = yawRotate(t.x * k, t.z * k);
                if (solid(pos.x + xz[0], pos.y + t.y * k, pos.z + xz[1])) {
                    hits++;
                    world.spawnParticle(Particle.CRIT, pos.x + xz[0], pos.y + t.y * k, pos.z + xz[1], 6, 0.3, 0.3, 0.3, 0.2);
                }
            }
            if (hits > 0) {
                world.playSound(base(), "minecraft:entity.item.break", SoundCategory.NEUTRAL, 1.5f, 0.6f);
                damage(hits * 2.5, null);
            }
        }
        if (pilot != null && ticks % 5 == 0) {
            double kmh = Math.hypot(vel.x, vel.z) * 20 * 3.6;
            int ground = groundBelow(64);
            String alt = ground == Integer.MIN_VALUE ? ">64" : String.valueOf((int) Math.round(pos.y - ground - 1));
            NamedTextColor hc = health > model.health * 0.6 ? NamedTextColor.GREEN
                    : health > model.health * 0.3 ? NamedTextColor.YELLOW : NamedTextColor.RED;
            pilot.sendActionBar(Component.text("Ротор " + (int) (rotor * 100) + "%  |  " + (int) kmh + " км/ч  |  высота "
                    + alt + " м  |  ", NamedTextColor.GRAY).append(Component.text("корпус " + (int) (health / model.health * 100) + "%", hc)));
        }
    }

    private int groundBelow(int range) {
        int x = (int) Math.floor(pos.x), z = (int) Math.floor(pos.z);
        for (int y = (int) Math.floor(pos.y); y > pos.y - range && y > world.getMinHeight(); y--) {
            Block b = world.getBlockAt(x, y, z);
            if (b.getType().isSolid() && !shell.contains(BlockKey.of(b))) return y;
        }
        return Integer.MIN_VALUE;
    }

    // ---------------------------------------------------------------- damage

    public void damage(double amount, Player attacker) {
        if (destroyed || amount <= 0) return;
        health -= amount;
        world.playSound(base(), "minecraft:entity.iron_golem.hurt", SoundCategory.NEUTRAL, 1f, 0.7f);
        if (health <= 0) destroy(true);
    }

    public void repair() {
        health = model.health;
    }

    /** Уничтожить: взрыв, выпадение груза, удаление из мира. */
    public void destroy(boolean explode) {
        if (destroyed) return;
        destroyed = true;
        Location c = worldPoint(new Vector3f(0, 16, 0));
        for (Player p : occupants()) p.leaveVehicle();
        if (explode) {
            world.spawnParticle(Particle.EXPLOSION_EMITTER, c, 3, 2, 1, 2, 0);
            world.spawnParticle(Particle.LARGE_SMOKE, c, 60, 3, 2, 3, 0.05);
            world.playSound(c, "minecraft:entity.generic.explode", SoundCategory.NEUTRAL, 4f, 0.7f);
        }
        for (ItemStack it : storage.getContents()) {
            if (it != null && !it.getType().isAir()) world.dropItemNaturally(c, it);
        }
        storage.clear();
        new ArrayList<>(storage.getViewers()).forEach(HumanEntity::closeInventory);
        clearShell();
        despawnEntities();
        plugin.manager().remove(this);
    }
}
