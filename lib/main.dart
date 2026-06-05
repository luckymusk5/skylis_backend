import 'package:flutter/material.dart';
import 'views/landing_page.dart';
import 'views/login_page.dart';
import 'views/skylist_search.dart'; // ← CORRIGÉ : enlève "_list"

void main() {
  runApp(const SkyLisApp());
}

class SkyLisApp extends StatelessWidget {
  const SkyLisApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SkyLis',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        fontFamily: 'Inter',
        primaryColor: const Color(0xFF059669),
        scaffoldBackgroundColor: const Color(0xFF06070b),
      ),
      home: const AppStateManager(),
    );
  }
}

class AppStateManager extends StatefulWidget {
  const AppStateManager({super.key});

  @override
  State<AppStateManager> createState() => _AppStateManagerState();
}

class _AppStateManagerState extends State<AppStateManager> {
  String step = 'landing';
  String authMode = 'signup';
  Map<String, String>? loggedInUser;

  @override
  Widget build(BuildContext context) {
    if (step == 'landing') {
      return LandingPage(
        onGetStarted: () {
          setState(() {
            authMode = 'signup';
            step = 'auth';
          });
        },
        onLoginClick: () {
          setState(() {
            authMode = 'login';
            step = 'auth';
          });
        },
      );
    }

    if (step == 'auth') {
      return LoginPage(
        mode: authMode,
        onSuccess: (userData) {
          setState(() {
            loggedInUser = userData;
            step = 'skylist';
          });
        },
        onBack: () {
          setState(() {
            step = 'landing';
          });
        },
      );
    }

    if (step == 'skylist') {
      final user = loggedInUser;
      if (user != null) {
        return SkyListSearch(
          user: user,
          onLogout: () {
            setState(() {
              loggedInUser = null;
              step = 'landing';
            });
          },
        );
      }
    }

    return const Scaffold(
      body: Center(child: CircularProgressIndicator(color: Color(0xFF059669))),
    );
  }
}
