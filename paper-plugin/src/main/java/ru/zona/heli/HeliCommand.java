package ru.zona.heli;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Location;
import org.bukkit.block.Block;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

import java.util.List;
import java.util.stream.Stream;

public final class HeliCommand implements CommandExecutor, TabCompleter {

    private static final List<String> SUBS = List.of("spawn", "remove", "list", "repair", "engine", "pack");
    private final HeliPlugin plugin;

    public HeliCommand(HeliPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        String sub = args.length > 0 ? args[0].toLowerCase() : "help";
        Player p = sender instanceof Player pl ? pl : null;
        switch (sub) {
            case "spawn" -> {
                if (!admin(sender) || p == null) return true;
                Block target = p.getTargetBlockExact(30);
                Location at = target != null ? target.getLocation().add(0.5, 1, 0.5) : p.getLocation();
                at.setYaw(p.getLocation().getYaw());
                plugin.manager().spawn(at);
                ok(sender, "Ми-8 создан. ПКМ по креслу пилота — сесть.");
            }
            case "remove" -> {
                if (!admin(sender) || p == null) return true;
                Helicopter h = plugin.manager().nearest(p.getLocation(), 30);
                if (h == null) { err(sender, "Рядом нет вертолёта"); return true; }
                h.destroy(false);
                ok(sender, "Вертолёт удалён (груз выпал рядом).");
            }
            case "repair" -> {
                if (!admin(sender) || p == null) return true;
                Helicopter h = plugin.manager().nearest(p.getLocation(), 30);
                if (h == null) { err(sender, "Рядом нет вертолёта"); return true; }
                h.repair();
                ok(sender, "Вертолёт отремонтирован.");
            }
            case "list" -> {
                if (!admin(sender)) return true;
                ok(sender, "Вертолётов: " + plugin.manager().all().size());
                for (Helicopter h : plugin.manager().all()) {
                    sender.sendMessage(Component.text(String.format(" • %s %.0f %.0f %.0f  корпус %.0f", h.world.getName(),
                            h.pos.x, h.pos.y, h.pos.z, h.health), NamedTextColor.GRAY));
                }
            }
            case "engine" -> {
                if (p == null) return true;
                Helicopter h = plugin.manager().byEntity(p.getVehicle());
                if (h == null || h.pilot() != p) { err(sender, "Нужно сидеть в кресле пилота"); return true; }
                h.engineOn = !h.engineOn;
                ok(sender, h.engineOn ? "Двигатели запущены" : "Двигатели выключены");
            }
            case "pack" -> {
                if (p == null) return true;
                plugin.packServer().send(p);
                ok(sender, "Ресурспак отправлен.");
            }
            default -> sender.sendMessage(Component.text(
                    "/heli spawn | remove | list | repair | engine | pack", NamedTextColor.YELLOW));
        }
        return true;
    }

    private boolean admin(CommandSender s) {
        if (s.hasPermission("heli.admin")) return true;
        err(s, "Нет прав (heli.admin)");
        return false;
    }

    private static void ok(CommandSender s, String msg) {
        s.sendMessage(Component.text(msg, NamedTextColor.GREEN));
    }

    private static void err(CommandSender s, String msg) {
        s.sendMessage(Component.text(msg, NamedTextColor.RED));
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 1) return SUBS.stream().filter(s -> s.startsWith(args[0].toLowerCase())).toList();
        return Stream.<String>empty().toList();
    }
}
