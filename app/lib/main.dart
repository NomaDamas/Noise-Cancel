import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import 'app_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const NoiseCancelAppRoot());
}

class NoiseCancelAppRoot extends StatelessWidget {
  const NoiseCancelAppRoot({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider<AppState>(
      create: (_) => AppState(),
      child: MaterialApp(
        title: 'NoiseCancel',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          brightness: Brightness.dark,
          scaffoldBackgroundColor: const Color(0xFF121212),
          cardColor: const Color(0xFF1E1E1E),
          colorScheme: ColorScheme.fromSeed(
            seedColor: Colors.blue,
            brightness: Brightness.dark,
          ),
          textTheme: GoogleFonts.spaceGroteskTextTheme(
            ThemeData(brightness: Brightness.dark).textTheme,
          ),
          useMaterial3: true,
        ),
        home: const _HomeScreen(),
      ),
    );
  }
}

class _HomeScreen extends StatelessWidget {
  const _HomeScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('NoiseCancel'),
      ),
      body: Center(
        child: Consumer<AppState>(
          builder: (context, appState, _) {
            return Text(
              appState.loading ? 'Loading posts...' : 'Feed scaffold ready',
            );
          },
        ),
      ),
    );
  }
}
