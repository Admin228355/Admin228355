/// Бренд и адреса TogetherForever.
///
/// Всё, что раньше смотрело на инфраструктуру автора Togetherly (сервер,
/// realtime, краш-репорты, поддержка), берётся отсюда. Сервер задаётся при
/// сборке: `--dart-define=PB_URL=https://твой-домен`. Realtime (Centrifugo)
/// по умолчанию живёт на том же домене — так его раздаёт `server/` из этого
/// репозитория, — и отдельно указывать его не нужно.
library;

class Brand {
  const Brand._();

  static const String appName = 'TogetherForever';

  /// Адрес своего PocketBase. Пусто — сборка без сервера, приложение
  /// покажет экран «сервер не настроен».
  static const String serverUrl = String.fromEnvironment('PB_URL');

  static bool get hasServer => serverUrl.isNotEmpty;

  /// Домен сервера без схемы: `example.duckdns.org`.
  static String get serverHost => Uri.tryParse(serverUrl)?.host ?? '';

  static const String _centrifugoWs = String.fromEnvironment('CENTRIFUGO_WS');

  /// WebSocket Centrifugo. По умолчанию — тот же домен, путь
  /// `/connection/websocket` (Caddy из `server/` проксирует его).
  static String get centrifugoWs {
    if (_centrifugoWs.isNotEmpty) return _centrifugoWs;
    final host = serverHost;
    return host.isEmpty ? '' : 'wss://$host/connection/websocket';
  }

  /// Репозиторий проекта: исходники, релизы, баги. CI подставляет свой.
  static const String repoUrl = String.fromEnvironment(
    'REPO_URL',
    defaultValue: 'https://github.com/Admin228355/Admin228355',
  );

  static const String issuesUrl = '$repoUrl/issues';

  /// Исходный проект, от которого сделан форк (GPL-3.0).
  static const String upstreamUrl = 'https://github.com/THET1ME-1/Togetherly';

  static String get privacyPolicyUrl => '$serverUrl/privacy-policy';
  static String get termsUrl => '$serverUrl/terms';
  static String inviteUrl(String code) => '$serverUrl/invite/$code';
}
