import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../services/api_service.dart';
import '../services/second_brain_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    FlutterSecureStorage? storage,
  }) : _storage = storage ?? const FlutterSecureStorage();

  static const ValueKey<String> serverUrlFieldKey = ValueKey<String>(
    'settings_server_url_field',
  );
  static const ValueKey<String> serverApiKeyFieldKey = ValueKey<String>(
    'settings_server_api_key_field',
  );
  static const ValueKey<String> secondBrainEnabledToggleKey = ValueKey<String>(
    'settings_second_brain_enabled_toggle',
  );
  static const ValueKey<String> secondBrainUrlFieldKey = ValueKey<String>(
    'settings_second_brain_url_field',
  );
  static const ValueKey<String> secondBrainApiKeyFieldKey = ValueKey<String>(
    'settings_second_brain_api_key_field',
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
  late final TextEditingController _serverApiKeyController;
  late final TextEditingController _secondBrainUrlController;
  late final TextEditingController _secondBrainApiKeyController;
  bool _secondBrainEnabled = false;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _serverUrlController = TextEditingController();
    _serverApiKeyController = TextEditingController();
    _secondBrainUrlController = TextEditingController();
    _secondBrainApiKeyController = TextEditingController();
    _loadSettings();
  }

  @override
  void dispose() {
    _serverUrlController.dispose();
    _serverApiKeyController.dispose();
    _secondBrainUrlController.dispose();
    _secondBrainApiKeyController.dispose();
    super.dispose();
  }

  Future<void> _loadSettings() async {
    try {
      final values = await Future.wait<String?>(<Future<String?>>[
        widget._storage.read(key: ApiService.serverUrlStorageKey),
        widget._storage.read(key: ApiService.apiKeyStorageKey),
        widget._storage.read(key: SecondBrainService.enabledStorageKey),
        widget._storage.read(key: SecondBrainService.urlStorageKey),
        widget._storage.read(key: SecondBrainService.apiKeyStorageKey),
      ]);

      if (!mounted) {
        return;
      }

      setState(() {
        _serverUrlController.text = values[0] ?? '';
        _serverApiKeyController.text = values[1] ?? '';
        _secondBrainEnabled = values[2] == 'true';
        _secondBrainUrlController.text = values[3] ?? '';
        _secondBrainApiKeyController.text = values[4] ?? '';
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
          key: ApiService.apiKeyStorageKey,
          value: _serverApiKeyController.text.trim(),
        ),
        widget._storage.write(
          key: SecondBrainService.enabledStorageKey,
          value: _secondBrainEnabled.toString(),
        ),
        widget._storage.write(
          key: SecondBrainService.urlStorageKey,
          value: _secondBrainUrlController.text.trim(),
        ),
        widget._storage.write(
          key: SecondBrainService.apiKeyStorageKey,
          value: _secondBrainApiKeyController.text.trim(),
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
                      const SizedBox(height: 12),
                      TextFormField(
                        key: SettingsScreen.serverApiKeyFieldKey,
                        controller: _serverApiKeyController,
                        obscureText: true,
                        decoration: const InputDecoration(
                          labelText: 'API Key',
                          hintText: 'Optional server API key',
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
                        'SecondBrain',
                        style:
                            Theme.of(context).textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                      ),
                      const SizedBox(height: 8),
                      SwitchListTile(
                        key: SettingsScreen.secondBrainEnabledToggleKey,
                        value: _secondBrainEnabled,
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Enable SecondBrain Sync'),
                        onChanged: (value) {
                          setState(() {
                            _secondBrainEnabled = value;
                          });
                        },
                      ),
                      const SizedBox(height: 8),
                      TextFormField(
                        key: SettingsScreen.secondBrainUrlFieldKey,
                        controller: _secondBrainUrlController,
                        decoration: const InputDecoration(
                          labelText: 'SecondBrain URL',
                          hintText: 'https://brain.example.com',
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        key: SettingsScreen.secondBrainApiKeyFieldKey,
                        controller: _secondBrainApiKeyController,
                        obscureText: true,
                        decoration: const InputDecoration(
                          labelText: 'API Key',
                          hintText: 'Your SecondBrain API key',
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
