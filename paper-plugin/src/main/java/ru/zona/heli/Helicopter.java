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
    private final Settings settings;
    public final HeliType type;
    public final UUID id;
    public World world;
    public final Vector3d pos = new Vector3d();
    public final Vector3d vel = new Vector3d();
    public float yaw;               // куда смотрит нос (как yaw игрока)
    private float pitch, roll, yawRate;
    public double rotor;            // 0..1 обороты винта
    public boolean engineOn;
    public double health;
    public final Map<String, Boolean> doorOpen = new LinkedHashMap<>();
    private final Map<String, Double> doorT = new HashMap<>();
    private final Map<String, Double> spinAngle = new HashMap<>();
    public boolean landed = true;
    private int noPilotTicks;
    private long ticks;
    public boolean destroyed;

    private final Inventory storage;
    private final Map<String, ItemDisplay> parts = new LinkedHashMap<>();
    private final List<ItemDisplay> seats = new ArrayList<>();
    private final Map<UUID, HeliType.Hotspot> hotspotByEntity = new HashMap<>();
    private final List<Interaction> hotspots = new ArrayList<>();
    public final Set<BlockKey> shell = new HashSet<>();
    private boolean shellDirty = true;
    private boolean spawned;

    public Helicopter(HeliPlugin plugin, HeliType type, UUID id, World world, double x, double y, double z, float yaw) {
        this.plugin = plugin;
        this.settings = plugin.settings();
        this.type = type;
        this.id = id;
        this.world = world;
        this.pos.set(x, y, z);
        this.yaw = yaw;
        this.health = type.flight.health();
        for (String d : type.doors.keySet()) {
            doorOpen.put(d, false);
            doorT.put(d, 0.0);
        }
        this.storage = Bukkit.createInventory(this, type.storageSize, Component.text(type.storageTitle));
    }

    @Override
    public Inventory getInventory() {
        return storage;
    }

    public boolean isOpen(String door) {
        return Boolean.TRUE.equals(doorOpen.get(door));
    }

    public void setOpen(String door, boolean open) {
        if (!doorOpen.containsKey(door)) return;
        doorOpen.put(door, open);
        doorT.put(door, open ? 1.0 : 0.0);
        shellDirty = true;
    }

    // ------------------------------------------------------------------ math

    /** Матрица корпуса: локальные блоки -> смещение от pos (рыскание + тангаж + крен). */
    private Matrix4f bodyMatrix() {
        Vector3f c = type.tiltCenter;
        return new Matrix4f()
                .rotateY((float) Math.toRadians(180.0 - yaw))
                .translate(c)
                .rotateX((float) Math.toRadians(-pitch))
                .rotateZ((float) Math.toRadians(-roll))
                .translate(-c.x, -c.y, -c.z);
    }

    /** Точка модели (единицы Blockbench) -> координаты мира. */
    public Location worldPoint(Vector3f units) {
        Vector3f v = bodyMatrix().transformPosition(type.toBlocks(units));
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
        for (HeliType.Part part : type.parts) {
            ItemDisplay d = world.spawn(base, ItemDisplay.class, e -> {
                ItemStack item = new ItemStack(Material.STICK);
                ItemMeta meta = item.getItemMeta();
                meta.setItemModel(new NamespacedKey("heli", part.key()));
                item.setItemMeta(meta);
                e.setItemStack(item);
                e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.NONE);
                e.setPersistent(false);
                e.setViewRange(settings.viewRange);
                e.setDisplayWidth(32f);
                e.setDisplayHeight(12f);
                e.setShadowRadius(0f);
                e.setTeleportDuration(2);
                e.setInterpolationDuration(2);
                e.getPersistentDataContainer().set(tag, PersistentDataType.STRING, id.toString());
            });
            parts.put(part.key(), d);
        }
        for (HeliType.Seat seat : type.seats) {
            ItemDisplay s = world.spawn(worldPoint(seat.pos()), ItemDisplay.class, e -> {
                e.setPersistent(false);
                e.setTeleportDuration(2);
                e.getPersistentDataContainer().set(tag, PersistentDataType.STRING, id.toString());
            });
            seats.add(s);
            plugin.manager().index(s, this);
        }
        for (HeliType.Hotspot h : type.hotspots) {
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

    private Location hotspotLocation(HeliType.Hotspot h) {
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

    private static Matrix4f axisRotate(Matrix4f m, char axis, double deg) {
        float r = (float) Math.toRadians(deg);
        return switch (axis) {
            case 'x' -> m.rotateX(r);
            case 'z' -> m.rotateZ(r);
            default -> m.rotateY(r);
        };
    }

    private void updateEntities(boolean force) {
        Matrix4f body = bodyMatrix();
        Location base = base();
        float bpu = (float) type.blocksPerUnit;
        for (HeliType.Part part : type.parts) {
            ItemDisplay d = parts.get(part.key());
            if (d == null) continue;
            Matrix4f m = new Matrix4f(body).translate(part.pivot());   // pivot уже в блоках
            double t = part.door() == null ? 0 : doorT.getOrDefault(part.door(), 0.0);
            switch (part.anim()) {
                case "spin" -> axisRotate(m, part.axis(), spinAngle.getOrDefault(part.key(), 0.0));
                case "hinge" -> axisRotate(m, part.axis(), part.angle() * ease(t));
                case "slide" -> {
                    double out = ease(Math.min(1, t / 0.25)), slide = ease(Math.max(0, (t - 0.25) / 0.75));
                    Vector3f o = part.out(), s = part.slide();
                    m.translate((float) (o.x * out + s.x * slide) * bpu, (float) (o.y * out + s.y * slide) * bpu,
                            (float) (o.z * out + s.z * slide) * bpu);
                }
                default -> { }
            }
            m.scale(type.displayScale).rotateY((float) Math.toRadians(settings.yawOffset));
            if (force || moving()) d.teleport(base);
            d.setInterpolationDelay(0);
            d.setTransformationMatrix(m);
        }
        for (int i = 0; i < seats.size(); i++) {
            Location l = worldPoint(type.seats.get(i).pos());
            l.setY(l.getY() + settings.seatYOffset);
            l.setYaw(yaw);
            seats.get(i).teleport(l, TeleportFlag.EntityState.RETAIN_PASSENGERS);
        }
        for (Interaction in : hotspots) {
            HeliType.Hotspot h = hotspotByEntity.get(in.getUniqueId());
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

    public HeliType.Hotspot hotspot(Entity e) {
        return hotspotByEntity.get(e.getUniqueId());
    }

    public void sit(Player p, int index) {
        if (index < 0 || index >= seats.size()) return;
        HeliType.Seat seat = type.seats.get(index);
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
            p.sendMessage(Component.text(type.name + ": вы пилот. Пробел — запуск/вверх, Shift — вниз (на земле — выйти), "
                    + "W/S — вперёд/назад, A/D — вбок, Ctrl — форсаж, поворот — мышью.", NamedTextColor.GREEN));
        } else {
            p.sendActionBar(Component.text("Место: " + seat.name(), NamedTextColor.GREEN));
        }
    }

    /** Куда высадить игрока после выхода. */
    public Location exitPoint() {
        Location l = worldPoint(shell.isEmpty() ? type.exitOutside : type.exitInside);
        l.setYaw(yaw);
        return l;
    }

    public List<Player> occupants() {
        List<Player> out = new ArrayList<>();
        for (ItemDisplay s : seats) for (Entity e : s.getPassengers()) if (e instanceof Player p) out.add(p);
        return out;
    }

    // ----------------------------------------------------------------- doors

    public void toggleDoor(String door, Player who) {
        HeliType.Door d = type.doors.get(door);
        if (d == null) return;
        boolean open = !isOpen(door);
        doorOpen.put(door, open);
        world.playSound(who.getLocation(), open ? d.openSound() : d.closeSound(), SoundCategory.BLOCKS, 1f, 0.8f);
        who.sendActionBar(Component.text(d.name() + (open ? ": открыта" : ": закрыта"), NamedTextColor.GRAY));
        shellDirty = true;
    }

    public void openStorage(Player who) {
        who.openInventory(storage);
        world.playSound(who.getLocation(), "minecraft:block.chest.open", SoundCategory.BLOCKS, 0.8f, 0.9f);
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
        Flight f = type.flight;

        if (pilot != null) {
            noPilotTicks = 0;
            if (!engineOn && in.isJump()) {
                engineOn = true;
                pilot.sendActionBar(Component.text("Запуск двигателей...", NamedTextColor.YELLOW));
            }
        } else if (landed && engineOn && ++noPilotTicks > settings.engineOffDelay) {
            engineOn = false;
        }
        rotor = engineOn ? Math.min(1, rotor + 1.0 / f.startupTicks()) : Math.max(0, rotor - 1.0 / f.shutdownTicks());

        physics(pilot, in, f);
        boolean doorsMoving = animate();
        updateShell();
        if (spawned && (moving() || rotor > 0 || doorsMoving || ticks % 40 == 0)) updateEntities(false);
        effects(pilot);
        if (ticks % 10 == 0) hints();
    }

    /** Подсказки «ПКМ — ...» игрокам, которые подошли к двери, сиденью или складу. */
    private void hints() {
        Location center = new Location(world, pos.x, pos.y, pos.z);
        for (Player p : world.getPlayers()) {
            if (p.isInsideVehicle() || p.getLocation().distanceSquared(center) > 18 * 18) continue;
            Location eye = p.getLocation();
            HeliType.Hotspot best = null;
            double bd = 2.4 * 2.4;
            for (HeliType.Hotspot h : type.hotspots) {
                Location l = hotspotLocation(h);
                double d = l.distanceSquared(eye);
                if (d < bd) {
                    bd = d;
                    best = h;
                }
            }
            if (best == null) continue;
            String text = switch (best.action()) {
                case DOOR -> {
                    HeliType.Door d = type.doors.get(best.door());
                    yield "[ПКМ] " + (isOpen(best.door()) ? "Закрыть: " : "Открыть: ") + (d == null ? "дверь" : d.name());
                }
                case STORAGE -> "[ПКМ] Открыть склад";
                case SEAT -> {
                    HeliType.Seat seat = type.seats.get(best.seat());
                    boolean busy = best.seat() < seats.size() && !seats.get(best.seat()).getPassengers().isEmpty();
                    yield busy ? seat.name() + ": занято" : "[ПКМ] Сесть: " + seat.name();
                }
            };
            p.sendActionBar(Component.text(text, NamedTextColor.YELLOW));
        }
    }

    private boolean animate() {
        for (HeliType.Part p : type.parts) {
            if ("spin".equals(p.anim())) {
                spinAngle.put(p.key(), (spinAngle.getOrDefault(p.key(), 0.0) + rotor * p.speed()) % 360);
            }
        }
        boolean moving = false;
        for (HeliType.Door d : type.doors.values()) {
            double cur = doorT.getOrDefault(d.id(), 0.0), target = isOpen(d.id()) ? 1 : 0;
            if (cur != target) {
                doorT.put(d.id(), approach(cur, target, 1.0 / Math.max(1, d.ticks())));
                moving = true;
            }
        }
        return moving;
    }

    private static double approach(double v, double target, double step) {
        return v < target ? Math.min(target, v + step) : Math.max(target, v - step);
    }

    // --------------------------------------------------------------- physics

    private void physics(Player pilot, Input in, Flight fl) {
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

        float before = yaw;
        if (pilot != null && rotor > 0.5) {
            float target = pilot.getLocation().getYaw();
            float diff = wrap(target - yaw);
            double rate = fl.turnRate() * (landed ? 0.35 : 1) * rotor;
            yaw = wrap(yaw + (float) clamp(diff, -rate, rate));
        }
        yawRate = wrap(yaw - before);

        double rad = Math.toRadians(yaw);
        double fx = -Math.sin(rad), fz = Math.cos(rad);          // вперёд
        double rx = -Math.cos(rad), rz = -Math.sin(rad);          // вправо
        double a = fl.accel() * lift * (boost ? fl.boost() : 1);
        if (!landed || up > 0) {
            vel.x += (fx * f * a) + (rx * s * fl.strafeAccel() * lift);
            vel.z += (fz * f * a) + (rz * s * fl.strafeAccel() * lift);
        }
        vel.y += up * fl.climbAccel() * lift - fl.gravity() * (1 - lift);
        if (lift >= 1 && up == 0) vel.y *= 0.8;                  // удержание высоты
        vel.x *= fl.drag();
        vel.z *= fl.drag();
        vel.y *= 0.93;
        double max = fl.maxSpeed() * (boost ? fl.boost() : 1);
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
            world.playSound(base(), "minecraft:block.anvil.land", SoundCategory.NEUTRAL, 0.4f, 0.6f);
        }
        landed = ground;
        if (landed) {
            vel.x *= 0.55;
            vel.z *= 0.55;
            if (vel.y < 0) vel.y = 0;
        }
        if (impact > fl.crashSpeed()) damage((impact - fl.crashSpeed()) * fl.crashDamage(), null);

        double targetPitch = landed ? 0 : f * 10 * lift + (h / Math.max(0.01, fl.maxSpeed())) * 3 * Math.signum(f);
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
        double k = type.blocksPerUnit;
        for (Vector3f p : type.collision) {
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
        boolean want = settings.shellEnabled && landed && !engineOn && rotor < 0.35;
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

    /** Невидимые барьеры по описанию типа (пол, борта, крыша, балка). Проёмы — там, где открыты двери. */
    private void rebuildShell() {
        Set<BlockKey> want = new HashSet<>();
        int bx = (int) Math.floor(pos.x), by = (int) Math.floor(pos.y), bz = (int) Math.floor(pos.z);
        for (int dx = -16; dx <= 16; dx++) {
            for (int dz = -16; dz <= 16; dz++) {
                double[] l = yawInverse(bx + dx + 0.5 - pos.x, bz + dz + 0.5 - pos.z);
                double mx = l[0] / type.blocksPerUnit, mz = l[1] / type.blocksPerUnit;
                for (int level = 0; level <= 4; level++) {
                    if (shellCell(mx, mz, level)) want.add(new BlockKey(bx + dx, by + level, bz + dz));
                }
            }
        }
        for (BlockKey k : new ArrayList<>(shell)) {
            if (!want.contains(k)) {
                Block b = world.getBlockAt(k.x(), k.y(), k.z());
                if (b.getType() == Material.BARRIER) b.setType(Material.AIR, false);
                shell.remove(k);
            }
        }
        for (BlockKey k : want) {
            if (shell.contains(k)) continue;
            Block b = world.getBlockAt(k.x(), k.y(), k.z());
            if (b.getType().isAir()) {
                b.setType(Material.BARRIER, false);
                shell.add(k);
            }
        }
        for (Player p : world.getPlayers()) {
            if (p.getLocation().distanceSquared(new Location(world, pos.x, pos.y, pos.z)) > 400) continue;
            if (p.isInsideVehicle()) continue;
            Block feet = p.getLocation().getBlock();
            if (shell.contains(BlockKey.of(feet))) p.teleport(p.getLocation().add(0, 1, 0));
        }
    }

    private boolean shellCell(double mx, double mz, int level) {
        for (HeliType.ShellBox b : type.shell) {
            if (level < b.l0() || level > b.l1()) continue;
            if (mx < b.x0() || mx > b.x1() || mz < b.z0() || mz > b.z1()) continue;
            if (b.door() != null && isOpen(b.door())) continue;
            return true;
        }
        return false;
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
            world.playSound(worldPoint(type.hub), settings.rotorSound, SoundCategory.NEUTRAL,
                    (float) (0.6 + rotor * 1.6), (float) (0.4 + rotor * 0.35));
        }
        if (settings.downwash && rotor > 0.6 && ticks % 2 == 0) {
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
        double maxHp = type.flight.health();
        if (health < maxHp * 0.4 && ticks % 3 == 0) {
            Location l = worldPoint(new Vector3f(type.hub.x, type.hub.y - 4, type.hub.z));
            world.spawnParticle(Particle.LARGE_SMOKE, l, 2, 0.4, 0.2, 0.4, 0.01);
        }
        if (settings.rotorStrike && rotor > 0.5 && ticks % 5 == 0) {
            int hits = 0;
            double k = type.blocksPerUnit;
            for (Vector3f t : type.rotorTips) {
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
            NamedTextColor hc = health > maxHp * 0.6 ? NamedTextColor.GREEN
                    : health > maxHp * 0.3 ? NamedTextColor.YELLOW : NamedTextColor.RED;
            pilot.sendActionBar(Component.text(type.name + "  |  ротор " + (int) (rotor * 100) + "%  |  " + (int) kmh
                    + " км/ч  |  высота " + alt + " м  |  ", NamedTextColor.GRAY)
                    .append(Component.text("корпус " + (int) (health / maxHp * 100) + "%", hc)));
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
        health = type.flight.health();
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
