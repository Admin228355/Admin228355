package ru.zona.heli;

import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.entity.EntityDismountEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.EquipmentSlot;

public final class HeliListener implements Listener {

    private final HeliPlugin plugin;

    public HeliListener(HeliPlugin plugin) {
        this.plugin = plugin;
    }

    /** ПКМ по хитбоксу: сесть, открыть дверь, открыть склад. */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onInteract(PlayerInteractEntityEvent e) {
        if (e.getHand() != EquipmentSlot.HAND) return;
        Entity clicked = e.getRightClicked();
        Helicopter h = plugin.manager().byEntity(clicked);
        if (h == null) return;
        e.setCancelled(true);
        Player p = e.getPlayer();
        if (!p.hasPermission("heli.use")) {
            p.sendActionBar(Component.text("Нет доступа к вертолёту", NamedTextColor.RED));
            return;
        }
        HeliType.Hotspot spot = h.hotspot(clicked);
        if (spot == null) {
            int seat = h.seatIndex(clicked);
            if (seat >= 0) h.sit(p, seat);
            return;
        }
        switch (spot.action()) {
            case SEAT -> h.sit(p, spot.seat());
            case DOOR -> h.toggleDoor(spot.door(), p);
            case STORAGE -> h.openStorage(p);
        }
    }

    /** ЛКМ по вертолёту — урон корпусу. */
    @EventHandler(ignoreCancelled = true)
    public void onAttack(PrePlayerAttackEntityEvent e) {
        Helicopter h = plugin.manager().byEntity(e.getAttacked());
        if (h == null) return;
        e.setCancelled(true);
        if (h.occupants().contains(e.getPlayer())) return;
        h.damage(2.0, e.getPlayer());
    }

    /** Выход из кресла: в полёте запрещён (Shift у пилота = снижение), на земле — высадка у двери. */
    @EventHandler(ignoreCancelled = true)
    public void onDismount(EntityDismountEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        Helicopter h = plugin.manager().byEntity(e.getDismounted());
        if (h == null || h.destroyed) return;
        if (!h.landed && !plugin.settings().allowJumpOut && p.isOnline() && !p.isDead()) {
            e.setCancelled(true);
            return;
        }
        Location exit = h.exitPoint();
        Bukkit.getScheduler().runTask(plugin, () -> {
            if (p.isOnline() && !p.isInsideVehicle()) p.teleport(exit);
        });
    }

    /** Барьеры вертолёта нельзя сломать. */
    @EventHandler(ignoreCancelled = true)
    public void onBreak(BlockBreakEvent e) {
        Helicopter.BlockKey k = new Helicopter.BlockKey(e.getBlock().getX(), e.getBlock().getY(), e.getBlock().getZ());
        for (Helicopter h : plugin.manager().all()) {
            if (h.world == e.getBlock().getWorld() && h.shell.contains(k)) {
                e.setCancelled(true);
                return;
            }
        }
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        plugin.packServer().send(e.getPlayer());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        Player p = e.getPlayer();
        if (plugin.manager().byEntity(p.getVehicle()) != null) p.leaveVehicle();
    }
}
