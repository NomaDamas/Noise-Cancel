import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../services/api_service.dart';
import '../services/webhook_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    FlutterSecureStorage? storage,
  }) : _storage = storage ?? const FlutterSecureStorage();

  static const ValueKey<String> serverUrlFieldKey = ValueKey<String>(
    'settings_server_url_field',
  );
  static const ValueKey<String> webhookEnabledToggleKey = ValueKey<String>(
    'settings_webhook_enabled_toggle',
  );
  static const ValueKey<String> webhookUrlFieldKey = ValueKey<String>(
    'settings_webhook_url_field',
  );
  static const ValueKey<String> webhookTemplateFieldKey = ValueKey<String>(
    'settings_webhook_template_field',
  );
  static const ValueKey<String> saveButtonKey = ValueKey<String>(
    'settings_save_button',
  );

  final FlutterSecureStorage _storage;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  static const Color _backgroundColor = Color(0xFF121212);
  static const Color _cardColor = Color(0xFF1E1E1E);

  late final TextEditingController _serverUrlController;
  late final TextEditingController _webhookUrlController;
  late final TextEditingController _webhookTemplateController;
  bool _webhookEnabled = false;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _serverUrlController = TextEditingController();
    _webhookUrlController = TextEditingController();
    _webhookTemplateController = TextEditingController();
    _loadSettings();
  }

  @override
  void dispose() {
    _serverUrlController.dispose();
    _webhookUrlController.dispose();
    _webhookTemplateController.dispose();
    super.dispose();
  }

  Future<void> _loadSettings() async {
    try {
      final values = await Future.wait<String?>(<Future<String?>>[
        widget._storage.read(key: ApiService.serverUrlStorageKey),
        widget._storage.read(key: WebhookService.webhookEnabledStorageKey),
        widget._storage.read(key: WebhookService.webhookUrlStorageKey),
        widget._storage.read(key: WebhookService.webhookTemplateStorageKey),
      ]);

      if (!mounted) {
        return;
      }

      setState(() {
        _serverUrlController.text = values[0] ?? '';
        _webhookEnabled = values[1] == 'true';
        _webhookUrlController.text = values[2] ?? '';
        _webhookTemplateController.text = values[3] ?? '';
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to load settings')),
      );
    }
  }

  Future<void> _saveSettings() async {
    setState(() {
      _isSaving = true;
    });

    try {
      await Future.wait<void>(<Future<void>>[
        widget._storage.write(
          key: ApiService.serverUrlStorageKey,
          value: _serverUrlController.text.trim(),
        ),
        widget._storage.write(
          key: WebhookService.webhookEnabledStorageKey,
          value: _webhookEnabled.toString(),
        ),
        widget._storage.write(
          key: WebhookService.webhookUrlStorageKey,
          value: _webhookUrlController.text.trim(),
        ),
        widget._storage.write(
          key: WebhookService.webhookTemplateStorageKey,
          value: _webhookTemplateController.text.trim(),
        ),
      ]);

      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Settings saved')),
      );
    } catch (_) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to save settings')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isSaving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _backgroundColor,
      appBar: AppBar(
        backgroundColor: _backgroundColor,
        foregroundColor: Colors.white,
        title: const Text('Settings'),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Card(
                color: _cardColor,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Server',
                        style:
                            Theme.of(context).textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        key: SettingsScreen.serverUrlFieldKey,
                        controller: _serverUrlController,
                        decoration: const InputDecoration(
                          labelText: 'Server URL',
                          hintText: 'http://localhost:8012',
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Card(
                color: _cardColor,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        'Webhook Configuration',
                        style:
                            Theme.of(context).textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                      ),
                      const SizedBox(height: 8),
                      SwitchListTile(
                        key: SettingsScreen.webhookEnabledToggleKey,
                        value: _webhookEnabled,
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Enable Webhook Forwarding'),
                        onChanged: (value) {
                          setState(() {
                            _webhookEnabled = value;
                          });
                        },
                      ),
                      const SizedBox(height: 8),
                      TextFormField(
                        key: SettingsScreen.webhookUrlFieldKey,
                        controller: _webhookUrlController,
                        decoration: const InputDecoration(
                          labelText: 'Webhook URL',
                          hintText: 'https://hooks.example.com/...',
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        key: SettingsScreen.webhookTemplateFieldKey,
                        controller: _webhookTemplateController,
                        minLines: 4,
                        maxLines: 8,
                        decoration: const InputDecoration(
                          labelText: 'JSON Payload Template',
                          hintText:
                              '{"summary":"{{summary}}","url":"{{post_url}}"}',
                          alignLabelWithHint: true,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                key: SettingsScreen.saveButtonKey,
                onPressed: _isSaving ? null : _saveSettings,
                child: Text(_isSaving ? 'Saving...' : 'Save'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
