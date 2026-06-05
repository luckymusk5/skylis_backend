import 'package:flutter/material.dart';

class LandingPage extends StatelessWidget {
  final VoidCallback onGetStarted;
  final VoidCallback onLoginClick;

  const LandingPage({
    super.key,
    required this.onGetStarted,
    required this.onLoginClick,
  });

  // Palette premium identique à ton thème React
  final Color bg = const Color(0xFF0a0b10);
  final Color text = const Color(0xFFf8fafc);
  final Color subText = const Color(0xFF94a3b8);
  final Color cardBg = const Color(0xFF121420);
  final Color border = const Color(0x14FFFFFF); // rgba(255,255,255,0.08)
  final Color accent = const Color(0xFF059669);

  @override
  Widget build(BuildContext context) {
    final double width = MediaQuery.of(context).size.width;
    final bool isDesktop = width >= 1024;

    return Scaffold(
      backgroundColor: bg,
      body: Stack(
        children: [
          // Éclat de lumière d'arrière-plan (Glow effect)
          Positioned(
            top: -150,
            left: width * 0.2,
            child: Container(
              width: 500,
              height: 500,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    accent.withValues(alpha: 0.12),
                    Colors.transparent,
                  ],
                ),
              ),
            ),
          ),

          // Contenu principal de la page
          Column(
            children: [
              // 1. BARRE DE NAVIGATION (Navbar)
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 40.0, vertical: 20.0),
                decoration: BoxDecoration(
                  color: bg.withValues(alpha: 0.8),
                  border: Border(bottom: BorderSide(color: border)),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Logo SkyLis
                    Row(
                      children: [
                        Container(
                          width: 32,
                          height: 32,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(10),
                            gradient: const LinearGradient(
                              colors: [Color(0xFF059669), Color(0xFF0284c7)],
                            ),
                          ),
                          child: const Icon(Icons.shield,
                              color: Colors.white, size: 16),
                        ),
                        const SizedBox(width: 12),
                        Text(
                          'SkyLis',
                          style: TextStyle(
                            color: text,
                            fontSize: 20,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.5,
                          ),
                        ),
                      ],
                    ),
                    // Boutons d'action
                    Row(
                      children: [
                        TextButton(
                          onPressed: onLoginClick,
                          child: Text(
                            'Connexion',
                            style: TextStyle(
                                color: subText, fontWeight: FontWeight.w600),
                          ),
                        ),
                        const SizedBox(width: 16),
                        ElevatedButton(
                          onPressed: onGetStarted,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: text,
                            foregroundColor: const Color(0xFF0f172a),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10)),
                            padding: const EdgeInsets.symmetric(
                                horizontal: 20, vertical: 12),
                          ),
                          child: const Text(
                            'Créer un compte',
                            style: TextStyle(fontWeight: FontWeight.w600),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              // 2. ZONE HERO RESPONSIVE (Deux colonnes si Desktop, une seule si Mobile)
              Expanded(
                child: SingleChildScrollView(
                  padding: EdgeInsets.symmetric(
                    horizontal: width > 1200 ? 120.0 : 40.0,
                    vertical: 60.0,
                  ),
                  child: isDesktop
                      ? Row(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: [
                            Expanded(child: _buildLeftColumn(isDesktop)),
                            const SizedBox(width: 80),
                            Expanded(child: _buildRightColumn()),
                          ],
                        )
                      : Column(
                          children: [
                            _buildLeftColumn(isDesktop),
                            const SizedBox(height: 80),
                            _buildRightColumn(),
                          ],
                        ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // Colonne de gauche : Textes et CTA
  Widget _buildLeftColumn(bool isDesktop) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Tag d'indexation certifiée
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          decoration: BoxDecoration(
            color: accent.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(100),
            border: Border.all(color: accent.withValues(alpha: 0.2)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.check_circle,
                  color: Color(0xFF34d399), size: 14),
              const SizedBox(width: 8),
              Text(
                'Indexation Certifiée Cameroun',
                style: TextStyle(
                    color: const Color(0xFF34d399),
                    fontSize: 13,
                    fontWeight: FontWeight.w700),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        // Titres principaux
        Text(
          'Achetez de manière sécurisée.',
          style: TextStyle(
            color: text,
            fontSize: isDesktop ? 48 : 36,
            fontWeight: FontWeight.w900,
            letterSpacing: -1.5,
            height: 1.1,
          ),
        ),
        ShaderMask(
          shaderCallback: (bounds) => const LinearGradient(
            colors: [Color(0xFF059669), Color(0xFF0284c7)],
          ).createShader(bounds),
          child: Text(
            'Traquez les vrais prix.',
            style: TextStyle(
              color: text,
              fontSize: isDesktop ? 48 : 36,
              fontWeight: FontWeight.w900,
              letterSpacing: -1.5,
              height: 1.1,
            ),
          ),
        ),
        const SizedBox(height: 24),
        // Paragraphe descriptif
        Text(
          'SkyLis élimine le chaos du e-commerce. Notre protocole filtre instantanément les arnaques, compare les stocks réels et calcule les frais de livraison exacts vers votre ville.',
          style: TextStyle(color: subText, fontSize: 17, height: 1.6),
        ),
        const SizedBox(height: 40),
        // Bouton principal
        InkWell(
          onTap: onGetStarted,
          borderRadius: BorderRadius.circular(12),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              gradient: const LinearGradient(
                  colors: [Color(0xFF059669), Color(0xFF0284c7)]),
              boxShadow: [
                BoxShadow(
                  color: accent.withValues(alpha: 0.3),
                  blurRadius: 24,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Lancer le comparateur',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.w700),
                ),
                const SizedBox(width: 12),
                Icon(Icons.arrow_forward, color: Colors.white, size: 18),
              ],
            ),
          ),
        ),
      ],
    );
  }

  // Colonne de droite : L'illustration centrale stylisée et ses 3 badges flottants
  Widget _buildRightColumn() {
    return Center(
      child: SizedBox(
        width: 420,
        height: 420,
        child: Stack(
          alignment: Alignment.center,
          children: [
            // Anneau décoratif externe
            Container(
              width: 320,
              height: 320,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: border),
                color: const Color(0xFF0d0e15),
              ),
            ),
            // Disque central (Shield Protocol)
            Container(
              width: 240,
              height: 240,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: cardBg,
                border: Border.all(color: border),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.4),
                    blurRadius: 40,
                    offset: const Offset(0, 20),
                  ),
                ],
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 64,
                    height: 64,
                    decoration: BoxDecoration(
                      color: accent.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Icon(Icons.fingerprint,
                        color: Color(0xFF34d399), size: 36),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'SHIELD PROTOCOL',
                    style: TextStyle(
                      color: subText,
                      fontSize: 11,
                      letterSpacing: 2.0,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    '100% Sécurisé',
                    style: TextStyle(
                        color: Color(0xFF34d399),
                        fontSize: 14,
                        fontWeight: FontWeight.w800),
                  ),
                ],
              ),
            ),

            // BADGE FLOTTANT 1 : Haut Gauche (Frais de livraison)
            Positioned(
              top: 20,
              left: 0,
              child: _buildFloatingBadge(
                child: Row(
                  children: [
                    const Icon(Icons.local_shipping,
                        color: Color(0xFF0284c7), size: 16),
                    const SizedBox(width: 10),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Frais de livraison',
                            style: TextStyle(
                                color: subText,
                                fontSize: 11,
                                fontWeight: FontWeight.w500)),
                        Text('Calculés en temps réel',
                            style: TextStyle(
                                color: text,
                                fontSize: 13,
                                fontWeight: FontWeight.w700)),
                      ],
                    ),
                  ],
                ),
              ),
            ),

            // BADGE FLOTTANT 2 : Bas Gauche (Douala & Yaoundé)
            Positioned(
              bottom: 40,
              left: -20,
              child: _buildFloatingBadge(
                child: Row(
                  children: [
                    Container(
                      width: 8,
                      height: 8,
                      decoration:
                          BoxDecoration(shape: BoxShape.circle, color: accent),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      'Douala & Yaoundé Inclus',
                      style: TextStyle(
                          color: text,
                          fontSize: 13,
                          fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
            ),

            // BADGE FLOTTANT 3 : Milieu Droite (Scanner les prix)
            Positioned(
              bottom: 150,
              right: -20,
              child: _buildFloatingBadge(
                child: Row(
                  children: [
                    const Icon(Icons.bolt, color: Colors.amber, size: 16),
                    const SizedBox(width: 8),
                    Text(
                      'Filtre Anti-Arnaque Actif',
                      style: TextStyle(
                          color: text,
                          fontSize: 12,
                          fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // Structure commune pour recréer l'effet "Card" sombre de tes composants React
  Widget _buildFloatingBadge({required Widget child}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.5),
            blurRadius: 30,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: child,
    );
  }
}
