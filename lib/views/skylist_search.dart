import 'package:flutter/material.dart';

class SkyListSearch extends StatefulWidget {
  final Map<String, String> user;
  final VoidCallback onLogout;

  const SkyListSearch({
    super.key,
    required this.user,
    required this.onLogout,
  });

  @override
  State<SkyListSearch> createState() => _SkyListSearchState();
}

class _SkyListSearchState extends State<SkyListSearch> {
  final TextEditingController _searchController = TextEditingController();
  String _currentCity = 'Douala';
  bool _isSearching = false;
  bool _hasSearched = false;
  List<Map<String, dynamic>> _results = [];

  final Color pageBg = const Color(0xFF06070b);
  final Color cardBg = const Color(0xFF0f121d);
  final Color headerBg = const Color(0xFF090a10);
  final Color textDark = const Color(0xFFFFFFFF);
  final Color textMuted = const Color(0xFF94a3b8);
  final Color inputBg = const Color(0xFF161a26);
  final Color inputBorder = const Color(0x0FFFFFFF);
  final Color accent = const Color(0xFF059669);
  final Color accentCyan = const Color(0xFF0284c7);

  @override
  void initState() {
    super.initState();
    _currentCity = widget.user['city'] ?? 'Douala';
    if (_currentCity.contains('(')) {
      _currentCity = _currentCity.split(' ')[0];
    }
  }

  void _executeSearch() async {
    if (_searchController.text.trim().isEmpty) return;

    setState(() {
      _isSearching = true;
      _hasSearched = true;
    });

    await Future.delayed(const Duration(milliseconds: 800));

    final query = _searchController.text.toLowerCase();
    final List<Map<String, dynamic>> newResults = [];

    if (query.contains('iphone') ||
        query.contains('telephone') ||
        query.contains('apple')) {
      newResults.addAll([
        {
          'id': 1,
          'product': 'Apple iPhone 15 Pro (256 Go) - Titane Noir',
          'platform': 'Glotelho.cm',
          'sellerType': 'Boutique Officielle Vérifiée 🛡️',
          'basePrice': '710,000 XAF',
          'deliveryCost': '1,500 XAF',
          'finalPrice': '711,500 XAF',
          'availability': 'Disponible immédiatement',
          'deliveryTime': 'Livraison aujourd\'hui',
        },
        {
          'id': 2,
          'product': 'Apple iPhone 15 Pro (256 Go) - Titane Naturel',
          'platform': 'Jumia Mall (Cameroun)',
          'sellerType': 'Vendeur Certifié Or 🛡️',
          'basePrice': '699,000 XAF',
          'deliveryCost': '4,500 XAF (Inter-villes)',
          'finalPrice': '703,500 XAF',
          'availability': 'En Stock à Douala',
          'deliveryTime': 'Livré en 48h max',
        },
      ]);
    } else if (query.isNotEmpty) {
      newResults.add({
        'id': 1,
        'product': '${_searchController.text} - Modèle Premium',
        'platform': 'Marketplace Nationale',
        'sellerType': 'Vendeur Vérifié SkyLis 🛡️',
        'basePrice': '45,000 XAF',
        'deliveryCost': '2,000 XAF',
        'finalPrice': '47,000 XAF',
        'availability': 'Disponible en stock',
        'deliveryTime': 'Livré en 24h',
      });
    }

    setState(() {
      _results = newResults;
      _isSearching = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: pageBg,
      body: Column(
        children: [
          // Header Navigation simplifié
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            color: headerBg,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    const Icon(Icons.bolt, color: Color(0xFF34d399), size: 20),
                    const SizedBox(width: 10),
                    const Text(
                      'SkyLis - Console d\'Indexation',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w800),
                    ),
                  ],
                ),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: const Color(0xFF161925),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.location_on,
                              color: Color(0xFF0284c7), size: 14),
                          const SizedBox(width: 6),
                          Text(
                            '${widget.user['name']} ($_currentCity)',
                            style: const TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                                fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 16),
                    IconButton(
                      onPressed: widget.onLogout,
                      icon: const Icon(Icons.power_settings_new,
                          color: Colors.redAccent, size: 20),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Main Content
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 40),
              child: Container(
                constraints: const BoxConstraints(maxWidth: 1000),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Titre
                    const Text(
                      'Protocole de Tri en Temps Réel',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 26,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -0.8),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Saisissez le nom d\'un article pour auditer la base de prix et calculer les charges d\'importation.',
                      style: TextStyle(color: textMuted, fontSize: 14),
                    ),
                    const SizedBox(height: 32),

                    // Barre de recherche
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: cardBg,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: inputBorder),
                      ),
                      child: LayoutBuilder(
                        builder: (context, constraints) {
                          final bool isMobile = constraints.maxWidth < 650;
                          return isMobile
                              ? Column(
                                  children: [
                                    _buildSearchInput(),
                                    const SizedBox(height: 12),
                                    _buildCityDropdown(),
                                    const SizedBox(height: 12),
                                    _buildSearchButton(),
                                  ],
                                )
                              : Row(
                                  children: [
                                    Expanded(
                                        flex: 2, child: _buildSearchInput()),
                                    _buildCityDropdown(),
                                    const SizedBox(width: 8),
                                    _buildSearchButton(),
                                  ],
                                );
                        },
                      ),
                    ),
                    const SizedBox(height: 40),

                    // Results Section
                    ..._buildResultsSection(),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchInput() {
    return Expanded(
      child: TextField(
        controller: _searchController,
        style: const TextStyle(color: Colors.white, fontSize: 14),
        decoration: InputDecoration(
          hintText:
              'Quel article recherchez-vous ? (ex: iPhone, PlayStation...)',
          hintStyle: TextStyle(color: textMuted.withOpacity(0.5), fontSize: 13),
          prefixIcon: Icon(Icons.search, color: textMuted, size: 20),
          border: InputBorder.none,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
        onSubmitted: (_) => _executeSearch(),
      ),
    );
  }

  Widget _buildCityDropdown() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: _currentCity,
          icon: const Icon(Icons.arrow_drop_down, color: Colors.white54),
          dropdownColor: cardBg,
          style: const TextStyle(
              color: Colors.white, fontWeight: FontWeight.w700, fontSize: 13),
          hint: const Text('Livrer à'),
          items: const [
            DropdownMenuItem(value: 'Douala', child: Text('Livrer à Douala')),
            DropdownMenuItem(value: 'Yaoundé', child: Text('Livrer à Yaoundé')),
            DropdownMenuItem(value: 'Garoua', child: Text('Livrer à Garoua')),
            DropdownMenuItem(
                value: 'Bafoussam', child: Text('Livrer à Bafoussam')),
            DropdownMenuItem(value: 'Bamenda', child: Text('Livrer à Bamenda')),
          ],
          onChanged: (value) {
            if (value != null) setState(() => _currentCity = value);
          },
        ),
      ),
    );
  }

  Widget _buildSearchButton() {
    return ElevatedButton(
      onPressed: _isSearching ? null : _executeSearch,
      style: ElevatedButton.styleFrom(
        backgroundColor: accent,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
      child: Text(
        _isSearching ? 'Scan en cours...' : 'Scanner le marché',
        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
      ),
    );
  }

  List<Widget> _buildResultsSection() {
    if (_isSearching) {
      return [
        const Center(
          child: Padding(
            padding: EdgeInsets.symmetric(vertical: 60),
            child: CircularProgressIndicator(color: Color(0xFF059669)),
          ),
        ),
      ];
    } else if (!_hasSearched) {
      return [
        Container(
          padding: const EdgeInsets.all(48),
          decoration: BoxDecoration(
            color: cardBg.withOpacity(0.4),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: accent.withOpacity(0.15)),
          ),
          child: Column(
            children: [
              Icon(Icons.query_stats, size: 48, color: accent.withOpacity(0.6)),
              const SizedBox(height: 16),
              const Text(
                'Aucun scan effectué',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 4),
              Text(
                'Lancez votre premier audit comparatif pour voir apparaître les coûts réels.',
                style: TextStyle(color: textMuted, fontSize: 13),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ];
    } else if (_results.isEmpty) {
      return [
        Container(
          padding: const EdgeInsets.all(48),
          child: Column(
            children: [
              const Icon(Icons.warning_amber_rounded,
                  size: 40, color: Colors.amber),
              const SizedBox(height: 16),
              const Text(
                'Aucune correspondance détectée',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 4),
              Text(
                'Essayez avec des mots-clés plus larges (ex: "iPhone" au lieu de la version exacte).',
                style: TextStyle(color: textMuted, fontSize: 13),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ];
    } else {
      return _results.map((item) => _buildResultCard(item)).toList();
    }
  }

  Widget _buildResultCard(Map<String, dynamic> item) {
    return Container(
      margin: const EdgeInsets.only(bottom: 18),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: inputBorder),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final bool isMobile = constraints.maxWidth < 600;
          return isMobile
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildCardLeftContent(item),
                    const SizedBox(height: 16),
                    const Divider(color: Colors.white10),
                    const SizedBox(height: 12),
                    _buildCardRightContent(item),
                  ],
                )
              : Row(
                  children: [
                    Expanded(flex: 2, child: _buildCardLeftContent(item)),
                    Container(
                      width: 1.5,
                      height: 80,
                      color: inputBorder,
                      margin: const EdgeInsets.symmetric(horizontal: 20),
                    ),
                    _buildCardRightContent(item),
                  ],
                );
        },
      ),
    );
  }

  Widget _buildCardLeftContent(Map<String, dynamic> item) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: const Color(0x1A34D399),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                item['trust'],
                style: const TextStyle(
                    color: Color(0xFF34d399),
                    fontSize: 10,
                    fontWeight: FontWeight.w800),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              item['stock'],
              style: TextStyle(
                color: item['stock'] == 'Disponible'
                    ? Colors.white70
                    : Colors.redAccent,
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Text(
          item['title'],
          style: const TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.3),
        ),
        const SizedBox(height: 4),
        Text(
          'Vendeur : ${item['vendor']}',
          style: TextStyle(
              color: textMuted, fontSize: 13, fontWeight: FontWeight.w500),
        ),
      ],
    );
  }

  Widget _buildCardRightContent(Map<String, dynamic> item) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Coût Réel Consolidé',
          style: TextStyle(
              color: Color(0xFF94a3b8),
              fontSize: 11,
              fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 2),
        Text(
          item['finalPrice'],
          style: TextStyle(
              color: accent,
              fontSize: 24,
              fontWeight: FontWeight.w900,
              fontFamily: 'monospace'),
        ),
        const SizedBox(height: 6),
        Text(
          'Base : ${item['basePrice']}\nLivr : ${item['deliveryCost']}',
          style: TextStyle(color: textMuted, fontSize: 12, height: 1.4),
        ),
      ],
    );
  }
}
