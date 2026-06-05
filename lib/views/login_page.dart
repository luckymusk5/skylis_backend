import 'package:flutter/material.dart';

class LoginPage extends StatefulWidget {
  final String mode;
  final Function(Map<String, String>) onSuccess;
  final VoidCallback onBack;

  const LoginPage({
    super.key,
    required this.mode,
    required this.onSuccess,
    required this.onBack,
  });

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  late String currentMode;
  final _formKey = GlobalKey<FormState>();

  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _nameController = TextEditingController();
  String _selectedCity = 'Douala (Littoral)';

  final Color pageBg = const Color(0xFF06070B);
  final Color leftPanelBg = const Color(0xFF0A0D1A);
  final Color cardBg = const Color(0xFF111827);
  final Color textMuted = const Color(0xFF94A3B8);
  final Color inputBg = const Color(0xFF1F2937);
  final Color inputBorder = const Color(0x1FFFFFFF);
  final Color accent = const Color(0xFF10B981);

  @override
  void initState() {
    super.initState();
    currentMode = widget.mode;
  }

  void _handleSubmit() {
    if (_formKey.currentState!.validate()) {
      widget.onSuccess({
        'name': currentMode == 'signup' ? _nameController.text : '',
        'city': _selectedCity,
        'email': _emailController.text,
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    final isWide = size.width > 900;

    return Scaffold(
      backgroundColor: pageBg,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: isWide ? _buildWideLayout() : _buildMobileLayout(),
          ),
        ),
      ),
    );
  }

  Widget _buildWideLayout() {
    return Container(
      width: 980,
      constraints: const BoxConstraints(maxHeight: 650),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.35), blurRadius: 40),
        ],
      ),
      child: Row(
        children: [
          // Panneau gauche
          Expanded(
            flex: 5,
            child: Container(
              decoration: BoxDecoration(
                color: leftPanelBg,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(28),
                  bottomLeft: Radius.circular(28),
                ),
              ),
              padding: const EdgeInsets.all(40),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text('SKYLIS PRO',
                      style: TextStyle(
                          color: accent,
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 2)),
                  const SizedBox(height: 20),
                  const Text('Welcome Portal',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 32,
                          fontWeight: FontWeight.w800,
                          height: 1.1)),
                  const SizedBox(height: 16),
                  Text(
                    'Connectez-vous pour accéder au traqueur de prix en temps réel et déjouer les fausses promotions sur les marchés du Cameroun.',
                    style: TextStyle(
                        color: textMuted, fontSize: 14.5, height: 1.45),
                  ),
                ],
              ),
            ),
          ),

          // Panneau droit
          Expanded(
            flex: 5,
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(36, 40, 36, 32),
              child: _buildFormContent(compact: true),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMobileLayout() {
    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(maxWidth: 420),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: _buildFormContent(compact: true),
      ),
    );
  }

  Widget _buildFormContent({bool compact = false}) {
    final double verticalSpacing = compact ? 16 : 20;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          currentMode == 'signup' ? 'Créer un compte' : 'Connexion',
          style: const TextStyle(
              color: Colors.white, fontSize: 24, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 6),
        Text(
          currentMode == 'signup'
              ? 'Rejoignez les acheteurs avertis en quelques clics.'
              : 'Accédez instantanément à votre tableau de bord.',
          style: TextStyle(color: textMuted, fontSize: 13.5),
        ),
        SizedBox(height: verticalSpacing + 8),
        Form(
          key: _formKey,
          child: Column(
            children: [
              if (currentMode == 'signup') ...[
                _buildField(_nameController, 'Prénom', Icons.person_outline,
                    hint: 'Ex: Christian'),
                SizedBox(height: verticalSpacing),
              ],
              _buildField(
                  _emailController, 'Adresse email', Icons.email_outlined,
                  hint: 'nom@exemple.com'),
              SizedBox(height: verticalSpacing),
              _buildField(
                  _passwordController, 'Mot de passe', Icons.lock_outline,
                  isPassword: true),
              if (currentMode == 'signup') ...[
                SizedBox(height: verticalSpacing),
                _buildCityDropdown(),
              ],
              SizedBox(height: verticalSpacing + 12),

              // Bouton plus compact
              Container(
                height: 50,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF10B981), Color(0xFF34D399)],
                  ),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: ElevatedButton(
                  onPressed: _handleSubmit,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.transparent,
                    shadowColor: Colors.transparent,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  child: Text(
                    currentMode == 'signup' ? "S'inscrire" : 'Se connecter',
                    style: const TextStyle(
                      fontSize: 15.5,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              currentMode == 'signup'
                  ? 'Déjà inscrit ?'
                  : 'Nouveau sur SkyLis ?',
              style: TextStyle(color: textMuted, fontSize: 13.5),
            ),
            TextButton(
              onPressed: () => setState(() =>
                  currentMode = currentMode == 'signup' ? 'login' : 'signup'),
              child: Text(
                currentMode == 'signup' ? 'Se connecter' : 'Créer un compte',
                style: TextStyle(color: accent, fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
        TextButton(
          onPressed: widget.onBack,
          child: Text('Retour au site',
              style: TextStyle(color: textMuted, fontSize: 13)),
        ),
      ],
    );
  }

  Widget _buildField(
      TextEditingController controller, String label, IconData icon,
      {bool isPassword = false, String hint = ''}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: TextStyle(
                color: textMuted, fontSize: 13, fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        TextFormField(
          controller: controller,
          obscureText: isPassword,
          style: const TextStyle(color: Colors.white, fontSize: 15),
          decoration: InputDecoration(
            filled: true,
            fillColor: inputBg,
            hintText: hint,
            hintStyle: TextStyle(color: textMuted.withOpacity(0.65)),
            prefixIcon: Icon(icon, color: textMuted, size: 19),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide.none,
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide(color: inputBorder),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide(color: accent, width: 1.6),
            ),
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 14,
              vertical: 14,
            ),
          ),
          validator: (value) {
            if (value == null || value.isEmpty) return 'Ce champ est requis';
            if (label.contains('email') && !value.contains('@')) {
              return 'Email invalide';
            }
            return null;
          },
        ),
      ],
    );
  }

  Widget _buildCityDropdown() {
    final cities = [
      'Douala (Littoral)',
      'Yaoundé (Centre)',
      'Bafoussam (Ouest)',
      'Garoua (Nord)'
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Ville de livraison',
            style: TextStyle(
                color: textMuted, fontSize: 13, fontWeight: FontWeight.w600)),
        const SizedBox(height: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14),
          decoration: BoxDecoration(
            color: inputBg,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: inputBorder),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: _selectedCity,
              isExpanded: true,
              icon: const Icon(Icons.keyboard_arrow_down,
                  color: Colors.white70, size: 20),
              dropdownColor: inputBg,
              style: const TextStyle(color: Colors.white, fontSize: 15),
              items: cities
                  .map((city) => DropdownMenuItem(
                        value: city,
                        child: Text(city),
                      ))
                  .toList(),
              onChanged: (value) => setState(() => _selectedCity = value!),
            ),
          ),
        ),
      ],
    );
  }
}
