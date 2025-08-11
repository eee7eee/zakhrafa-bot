
// lib/main.dart
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';
import 'package:url_launcher/url_launcher.dart';
import 'dart:io';

// ===== ألوان التطبيق =====
const Color lemonGreen = Color(0xFF9ACD32);
const Color lemonDark = Color(0xFF7BB01E);

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await DBHelper.instance.initDB();
  runApp(InstallmentApp());
}

class InstallmentApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "أقساط ليمونة 🍋🟩",
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        primaryColor: lemonGreen,
        colorScheme: ColorScheme.fromSeed(seedColor: lemonGreen),
        appBarTheme: AppBarTheme(
          backgroundColor: lemonGreen,
          titleTextStyle: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
          iconTheme: IconThemeData(color: Colors.white),
        ),
      ),
      home: HomeScreen(),
    );
  }
}

/* ===========================
   Models
   =========================== */
class Contract {
  int? id;
  String customerName;
  String phoneNumber; // with country code, e.g. 9647701234567
  String deviceModel;
  int officialPrice;
  int totalPrice;
  int downPayment;
  int monthlyInstallment;
  int remainingAmount;
  int contractMonths;
  String startDate;

  Contract({
    this.id,
    required this.customerName,
    required this.phoneNumber,
    required this.deviceModel,
    required this.officialPrice,
    required this.totalPrice,
    required this.downPayment,
    required this.monthlyInstallment,
    required this.remainingAmount,
    required this.contractMonths,
    required this.startDate,
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'customerName': customerName,
      'phoneNumber': phoneNumber,
      'deviceModel': deviceModel,
      'officialPrice': officialPrice,
      'totalPrice': totalPrice,
      'downPayment': downPayment,
      'monthlyInstallment': monthlyInstallment,
      'remainingAmount': remainingAmount,
      'contractMonths': contractMonths,
      'startDate': startDate
    };
  }

  static Contract fromMap(Map<String, dynamic> m) {
    return Contract(
      id: m['id'],
      customerName: m['customerName'],
      phoneNumber: m['phoneNumber'],
      deviceModel: m['deviceModel'],
      officialPrice: m['officialPrice'],
      totalPrice: m['totalPrice'],
      downPayment: m['downPayment'],
      monthlyInstallment: m['monthlyInstallment'],
      remainingAmount: m['remainingAmount'],
      contractMonths: m['contractMonths'],
      startDate: m['startDate'],
    );
  }
}

class Payment {
  int? id;
  int contractId;
  String date; // ISO string
  int amount;
  String method;
  String note;

  Payment({
    this.id,
    required this.contractId,
    required this.date,
    required this.amount,
    this.method = "نقدي",
    this.note = "",
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'contractId': contractId,
      'date': date,
      'amount': amount,
      'method': method,
      'note': note,
    };
  }

  static Payment fromMap(Map<String, dynamic> m) {
    return Payment(
      id: m['id'],
      contractId: m['contractId'],
      date: m['date'],
      amount: m['amount'],
      method: m['method'],
      note: m['note'],
    );
  }
}

/* ===========================
   DB Helper (sqflite)
   =========================== */
class DBHelper {
  DBHelper._private();
  static final DBHelper instance = DBHelper._private();

  Database? _db;

  Future<void> initDB() async {
    if (_db != null) return;
    Directory documentsDirectory = await getApplicationDocumentsDirectory();
    String path = p.join(documentsDirectory.path, "lemon_installments.db");
    _db = await openDatabase(
      path,
      version: 1,
      onCreate: _onCreate,
    );
  }

  Future _onCreate(Database db, int version) async {
    await db.execute('''
      CREATE TABLE contracts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customerName TEXT,
        phoneNumber TEXT,
        deviceModel TEXT,
        officialPrice INTEGER,
        totalPrice INTEGER,
        downPayment INTEGER,
        monthlyInstallment INTEGER,
        remainingAmount INTEGER,
        contractMonths INTEGER,
        startDate TEXT
      )
    ''');

    await db.execute('''
      CREATE TABLE payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contractId INTEGER,
        date TEXT,
        amount INTEGER,
        method TEXT,
        note TEXT,
        FOREIGN KEY(contractId) REFERENCES contracts(id) ON DELETE CASCADE
      )
    ''');
  }

  Future<int> insertContract(Contract c) async {
    final db = _db!;
    return await db.insert('contracts', c.toMap());
  }

  Future<int> updateContract(Contract c) async {
    final db = _db!;
    return await db.update('contracts', c.toMap(), where: 'id = ?', whereArgs: [c.id]);
  }

  Future<int> deleteContract(int id) async {
    final db = _db!;
    // delete payments first (cascade may not work on sqlite default in Android)
    await db.delete('payments', where: 'contractId = ?', whereArgs: [id]);
    return await db.delete('contracts', where: 'id = ?', whereArgs: [id]);
  }

  Future<List<Contract>> getAllContracts() async {
    final db = _db!;
    final rows = await db.query('contracts', orderBy: 'id DESC');
    return rows.map((r) => Contract.fromMap(r)).toList();
  }

  Future<Contract?> getContractById(int id) async {
    final db = _db!;
    final rows = await db.query('contracts', where: 'id = ?', whereArgs: [id]);
    if (rows.isEmpty) return null;
    return Contract.fromMap(rows.first);
  }

  Future<int> insertPayment(Payment p) async {
    final db = _db!;
    return await db.insert('payments', p.toMap());
  }

  Future<List<Payment>> getPaymentsForContract(int contractId) async {
    final db = _db!;
    final rows = await db.query('payments', where: 'contractId = ?', whereArgs: [contractId], orderBy: 'date DESC');
    return rows.map((r) => Payment.fromMap(r)).toList();
  }

  Future<int> deletePayment(int id) async {
    final db = _db!;
    return await db.delete('payments', where: 'id = ?', whereArgs: [id]);
  }

  // Monthly report: sum of all totals, sum of payments in month, expected next payments etc.
  Future<Map<String, int>> monthlySummary({required int year, required int month}) async {
    final db = _db!;
    final start = DateTime(year, month, 1);
    final end = DateTime(year, month + 1, 1);
    final paymentsRows = await db.rawQuery('SELECT SUM(amount) as totalReceived FROM payments WHERE date >= ? AND date < ?', [start.toIso8601String(), end.toIso8601String()]);
    final totalReceived = paymentsRows.first['totalReceived'] as int? ?? 0;

    final allContracts = await db.query('contracts');
    int totalGranted = 0;
    int totalRemaining = 0;
    int totalExpectedInMonth = 0;

    for (final c in allContracts) {
      totalGranted += (c['totalPrice'] as int);
      totalRemaining += (c['remainingAmount'] as int);

      // simplistic expected: if monthlyInstallment >0, assume each contract contributes monthlyInstallment
      totalExpectedInMonth += (c['monthlyInstallment'] as int);
    }

    // profit estimate = totalGranted - sum(officialPrice)
    int sumOfficial = 0;
    for (final c in allContracts) {
      sumOfficial += (c['officialPrice'] as int);
    }
    int expectedProfit = totalGranted - sumOfficial;

    return {
      'totalGranted': totalGranted,
      'totalReceived': totalReceived,
      'totalRemaining': totalRemaining,
      'expectedProfit': expectedProfit,
      'expectedMonthly': totalExpectedInMonth,
    };
  }
}

/* ===========================
   Utilities
   =========================== */
String fmtDate(String iso) {
  final dt = DateTime.parse(iso);
  return DateFormat('yyyy-MM-dd – kk:mm').format(dt);
}

String fmtShortDate(String iso) {
  final dt = DateTime.parse(iso);
  return DateFormat('yyyy-MM-dd').format(dt);
}

String currency(int v) {
  final fmt = NumberFormat.decimalPattern();
  return fmt.format(v) + " د.ع";
}

/* ===========================
   Home screen (list + top summary)
   =========================== */
class HomeScreen extends StatefulWidget {
  @override
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<Contract> contracts = [];
  bool loading = true;
  int totalGranted = 0;
  int totalReceived = 0;
  int totalRemaining = 0;
  int expectedProfit = 0;
  int expectedMonthly = 0;

  @override
  void initState() {
    super.initState();
    _loadAll();
  }

  Future<void> _loadAll() async {
    setState(() => loading = true);
    contracts = await DBHelper.instance.getAllContracts();
    final now = DateTime.now();
    final summary = await DBHelper.instance.monthlySummary(year: now.year, month: now.month);
    setState(() {
      totalGranted = summary['totalGranted'] ?? 0;
      totalReceived = summary['totalReceived'] ?? 0;
      totalRemaining = summary['totalRemaining'] ?? 0;
      expectedProfit = summary['expectedProfit'] ?? 0;
      expectedMonthly = summary['expectedMonthly'] ?? 0;
      loading = false;
    });
  }

  void _openAddContract() async {
    final res = await Navigator.push(context, MaterialPageRoute(builder: (_) => AddContractScreen()));
    if (res == true) await _loadAll();
  }

  void _openDetails(Contract c) async {
    final res = await Navigator.push(context, MaterialPageRoute(builder: (_) => ContractDetailsPage(contractId: c.id!)));
    if (res == true) await _loadAll();
  }

  void _openReport() async {
    final now = DateTime.now();
    Navigator.push(context, MaterialPageRoute(builder: (_) => MonthlyReportScreen(contractsListFuture: DBHelper.instance.getAllContracts(), year: now.year, month: now.month)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("أقساط ليمونة 🍋🟩"),
        actions: [
          IconButton(icon: Icon(Icons.refresh), onPressed: _loadAll),
          IconButton(icon: Icon(Icons.bar_chart), onPressed: _openReport),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openAddContract,
        backgroundColor: lemonDark,
        icon: Icon(Icons.add),
        label: Text("عقد جديد"),
      ),
      body: loading
          ? Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadAll,
              child: ListView(
                padding: EdgeInsets.all(12),
                children: [
                  _buildTopSummary(),
                  SizedBox(height: 12),
                  ...contracts.map((c) => _contractCard(c)).toList(),
                  if (contracts.isEmpty)
                    Padding(
                      padding: const EdgeInsets.all(20.0),
                      child: Center(child: Text("لا توجد عقود بعد — أضف عقد جديد للبدء", style: TextStyle(color: Colors.grey[700]))),
                    ),
                  SizedBox(height: 80),
                ],
              ),
            ),
    );
  }

  Widget _buildTopSummary() {
    return Card(
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: EdgeInsets.symmetric(vertical: 12, horizontal: 14),
        child: Row(
          children: [
            CircleAvatar(radius: 28, backgroundColor: lemonGreen.withOpacity(0.18), child: Text("🍋", style: TextStyle(fontSize: 24))),
            SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text("ملف المدير — ملخص شهري", style: TextStyle(fontWeight: FontWeight.bold)),
                SizedBox(height: 6),
                Text("عقود مُدارة: ${contracts.length} • المتوقَّع هذا الشهر: ${currency(expectedMonthly)}", style: TextStyle(fontSize: 12)),
              ]),
            ),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text("المستلم: ${currency(totalReceived)}", style: TextStyle(fontWeight: FontWeight.bold)),
              SizedBox(height: 6),
              Text("المتبقي: ${currency(totalRemaining)}", style: TextStyle(color: Colors.red[700])),
              SizedBox(height: 6),
              Text("أرباح مبدئية: ${currency(expectedProfit)}", style: TextStyle(color: Colors.green[800])),
            ])
          ],
        ),
      ),
    );
  }

  Widget _contractCard(Contract c) {
    final percent = (c.totalPrice - c.remainingAmount) / (c.totalPrice == 0 ? 1 : c.totalPrice);
    return Padding(
      padding: EdgeInsets.symmetric(vertical: 8),
      child: InkWell(
        onTap: () => _openDetails(c),
        borderRadius: BorderRadius.circular(12),
        child: Card(
          elevation: 4,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          child: Padding(
            padding: EdgeInsets.all(12),
            child: Row(children: [
              CircleAvatar(radius: 30, backgroundColor: lemonGreen.withOpacity(0.12), child: Icon(Icons.phone_android, size: 28, color: lemonGreen)),
              SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Expanded(child: Text(c.customerName, style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold))),
                    Text(currency(c.remainingAmount), style: TextStyle(color: c.remainingAmount > 500000 ? Colors.red : Colors.green, fontWeight: FontWeight.bold)),
                  ]),
                  SizedBox(height: 6),
                  Text(c.deviceModel, style: TextStyle(color: Colors.grey[700])),
                  SizedBox(height: 8),
                  LinearProgressIndicator(value: percent, backgroundColor: Colors.grey[300], valueColor: AlwaysStoppedAnimation(lemonGreen)),
                  SizedBox(height: 6),
                  Text("قسط/شهر: ${currency(c.monthlyInstallment)} • المجموع: ${currency(c.totalPrice)}", style: TextStyle(fontSize: 12, color: Colors.grey[600])),
                ]),
              ),
              Icon(Icons.chevron_left, color: lemonDark),
            ]),
          ),
        ),
      ),
    );
  }
}

/* ===========================
   Add Contract Screen
   (labels above fields, no example inside)
   =========================== */
class AddContractScreen extends StatefulWidget {
  @override
  _AddContractScreenState createState() => _AddContractScreenState();
}

class _AddContractScreenState extends State<AddContractScreen> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController nameCtl = TextEditingController();
  final TextEditingController phoneCtl = TextEditingController();
  final TextEditingController deviceCtl = TextEditingController();
  final TextEditingController officialPriceCtl = TextEditingController();
  final TextEditingController rateCtl = TextEditingController(text: "0");
  final TextEditingController monthsCtl = TextEditingController(text: "12");
  final TextEditingController downCtl = TextEditingController(text: "0");

  bool loading = false;

  @override
  void dispose() {
    nameCtl.dispose();
    phoneCtl.dispose();
    deviceCtl.dispose();
    officialPriceCtl.dispose();
    rateCtl.dispose();
    monthsCtl.dispose();
    downCtl.dispose();
    super.dispose();
  }

  void _save() async {
    if (!_formKey.currentState!.validate()) return;
    final name = nameCtl.text.trim();
    final phone = phoneCtl.text.trim();
    final device = deviceCtl.text.trim();
    final officialPrice = int.parse(officialPriceCtl.text.trim());
    final rate = double.tryParse(rateCtl.text.trim()) ?? 0.0;
    final months = int.parse(monthsCtl.text.trim());
    final down = int.tryParse(downCtl.text.trim());

    final interest = (officialPrice * (rate / 100)).round();
    final total = officialPrice + interest;
    final remaining = total - (down ?? 0);
    final monthly = (total / months).round();

    final c = Contract(
      customerName: name,
      phoneNumber: phone,
      deviceModel: device,
      officialPrice: officialPrice,
      totalPrice: total,
      downPayment: down ?? 0,
      monthlyInstallment: monthly,
      remainingAmount: remaining,
      contractMonths: months,
      startDate: DateTime.now().toIso8601String(),
    );

    setState(() => loading = true);
    final id = await DBHelper.instance.insertContract(c);
    setState(() => loading = false);
    Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("إضافة عقد جديد"),
      ),
      body: Padding(
        padding: EdgeInsets.all(12),
        child: Form(
          key: _formKey,
          child: ListView(children: [
            Text("اسم العميل", style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 6),
            TextFormField(controller: nameCtl, decoration: InputDecoration(border: OutlineInputBorder()), validator: (v) => v == null || v.trim().isEmpty ? "أدخل اسم العميل" : null),
            SizedBox(height: 12),

            Text("رقم الهاتف (مع رمز الدولة)", style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 6),
            TextFormField(controller: phoneCtl, keyboardType: TextInputType.phone, decoration: InputDecoration(border: OutlineInputBorder()), validator: (v) => v == null || v.trim().isEmpty ? "أدخل رقم الهاتف" : null),
            SizedBox(height: 12),

            Text("اسم الجهاز / الموديل", style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 6),
            TextFormField(controller: deviceCtl, decoration: InputDecoration(border: OutlineInputBorder()), validator: (v) => v == null || v.trim().isEmpty ? "أدخل موديل الجهاز" : null),
            SizedBox(height: 12),

            Text("السعر الرسمي (د.ع)", style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 6),
            TextFormField(controller: officialPriceCtl, keyboardType: TextInputType.number, decoration: InputDecoration(border: OutlineInputBorder()), validator: (v) => v == null || v.trim().isEmpty ? "أدخل السعر الرسمي" : null),
            SizedBox(height: 12),

            Text("نسبة الفائدة (%)", style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 6),
            TextFormField(controller: rateCtl, keyboardType: TextInputType.number, decoration: InputDecoration(border: OutlineInputBorder()), validator: (v) => v == null || v.trim().isEmpty ? "أدخل نسبة الفائدة" : null),
            SizedBox(height: 12),

            Text("المدة (شهر)", style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 6),
            TextFormField(controller: monthsCtl, keyboardType: TextInputType.number, decoration: InputDecoration(border: OutlineInputBorder()), validator: (v) => v == null || v.trim().isEmpty ? "أدخل المدة بالأشهر" : null),
            SizedBox(height: 12),

            Text("المقدم المدفوع (د.ع) إن وجد", style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 6),
            TextFormField(controller: downCtl, keyboardType: TextInputType.number, decoration: InputDecoration(border: OutlineInputBorder()), validator: (v) => null),
            SizedBox(height: 16),

            ElevatedButton.icon(onPressed: _save, icon: Icon(Icons.save), label: Text("حفظ العقد")),
            if (loading) SizedBox(height: 12),
            if (loading) Center(child: CircularProgressIndicator()),
          ]),
        ),
      ),
    );
  }
}

/* ===========================
   Contract Details Page (view/add payment/delete)
   =========================== */
class ContractDetailsPage extends StatefulWidget {
  final int contractId;

  ContractDetailsPage({required this.contractId});

  @override
  _ContractDetailsPageState createState() => _ContractDetailsPageState();
}

class _ContractDetailsPageState extends State<ContractDetailsPage> {
  Contract? contract;
  List<Payment> payments = [];
  bool loading = true;

  final TextEditingController amountCtl = TextEditingController();
  final TextEditingController methodCtl = TextEditingController(text: "نقدي");
  final TextEditingController noteCtl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => loading = true);
    contract = await DBHelper.instance.getContractById(widget.contractId);
    payments = await DBHelper.instance.getPaymentsForContract(widget.contractId);
    setState(() => loading = false);
  }

  Future<void> _addPayment() async {
    if (amountCtl.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("أدخل مبلغ الدفع")));
      return;
    }
    final amt = int.parse(amountCtl.text.trim());
    final p = Payment(contractId: contract!.id!, date: DateTime.now().toIso8601String(), amount: amt, method: methodCtl.text.trim(), note: noteCtl.text.trim());
    await DBHelper.instance.insertPayment(p);

    // update remaining amount in contract
    contract!.remainingAmount = (contract!.remainingAmount - amt).clamp(0, 999999999);
    await DBHelper.instance.updateContract(contract!);

    // send whatsapp confirmation
    _sendWhatsAppPaymentConfirmation(amt, contract!);

    amountCtl.clear();
    noteCtl.clear();

    await _load();
  }

  Future<void> _sendWhatsAppPaymentConfirmation(int paidAmount, Contract c) async {
    final date = DateFormat('yyyy-MM-dd – kk:mm').format(DateTime.now());
    final msg = Uri.encodeComponent("مرحباً ${c.customerName}، تم استلام دفعة بقيمة ${paidAmount} د.ع بتاريخ ${date}.\nالمتبقي الآن: ${c.remainingAmount} د.ع.\nشكراً لتعاملكم مع أقساط ليمونة 🍋🟩");
    final uri = Uri.parse("https://wa.me/${c.phoneNumber}?text=$msg");

    try {
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      } else {
        final webUri = Uri.parse("https://api.whatsapp.com/send?phone=${c.phoneNumber}&text=${msg}");
        if (await canLaunchUrl(webUri)) {
          await launchUrl(webUri, mode: LaunchMode.externalApplication);
        }
      }
    } catch (e) {
      // silent fail — show snackbar
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("فشل إرسال رسالة واتساب (قد لا يكون واتساب منصب)")));
    }
  }

  Future<void> _deleteContract() async {
    final ok = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
              title: Text("تأكيد الحذف"),
              content: Text("هل تريد حذف هذا العقد وكل دفعاته نهائياً؟ هذه العملية لا يمكن التراجع عنها."),
              actions: [
                TextButton(onPressed: () => Navigator.pop(context, false), child: Text("إلغاء")),
                TextButton(onPressed: () => Navigator.pop(context, true), child: Text("حذف", style: TextStyle(color: Colors.red)))
              ],
            ));
    if (ok == true) {
      await DBHelper.instance.deleteContract(contract!.id!);
      Navigator.pop(context, true); // inform previous to refresh
    }
  }

  Future<void> _deletePayment(int payId, int amount) async {
    final ok = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
              title: Text("تأكيد حذف الدفعة"),
              content: Text("هل تريد حذف هذه الدفعة؟ سيتم ترجيع المبلغ إلى المتبقي."),
              actions: [
                TextButton(onPressed: () => Navigator.pop(context, false), child: Text("إلغاء")),
                TextButton(onPressed: () => Navigator.pop(context, true), child: Text("حذف", style: TextStyle(color: Colors.red)))
              ],
            ));
    if (ok == true) {
      await DBHelper.instance.deletePayment(payId);
      // revert remaining amount
      contract!.remainingAmount = contract!.remainingAmount + amount;
      await DBHelper.instance.updateContract(contract!);
      await _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return Scaffold(appBar: AppBar(title: Text("تفاصيل العقد")), body: Center(child: CircularProgressIndicator()));
    if (contract == null) return Scaffold(appBar: AppBar(title: Text("تفاصيل العقد")), body: Center(child: Text("العقد غير موجود")));

    final interest = contract!.totalPrice - contract!.officialPrice;

    return Scaffold(
      appBar: AppBar(
        title: Text("تفاصيل العقد"),
        actions: [
          IconButton(icon: Icon(Icons.delete_forever), onPressed: _deleteContract),
        ],
      ),
      body: Padding(
        padding: EdgeInsets.all(12),
        child: ListView(children: [
          Row(children: [
            CircleAvatar(radius: 36, backgroundColor: lemonGreen.withOpacity(0.12), child: Icon(Icons.phone_iphone, color: lemonGreen, size: 32)),
            SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(contract!.customerName, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)), SizedBox(height: 6), Text(contract!.deviceModel)])),
            IconButton(
                icon: Icon(Icons.whatsapp, color: lemonGreen),
                onPressed: () {
                  // open quick share of contract details via whatsapp
                  final msg = Uri.encodeComponent("""
تفاصيل عقد التقسيط:
العميل: ${contract!.customerName}
الهاتف: ${contract!.phoneNumber}
الجهاز: ${contract!.deviceModel}
السعر الرسمي: ${contract!.officialPrice} د.ع
السعر مع الفائدة: ${contract!.totalPrice} د.ع
الفائدة: ${interest} د.ع
المقدم: ${contract!.downPayment} د.ع
القسط الشهري: ${contract!.monthlyInstallment} د.ع
المتبقي: ${contract!.remainingAmount} د.ع
بداية العقد: ${fmtShortDate(contract!.startDate)}
مدة العقد: ${contract!.contractMonths} شهر
""");
                  final uri = Uri.parse("https://wa.me/${contract!.phoneNumber}?text=$msg");
                  launchUrl(uri);
                })
          ]),
          SizedBox(height: 12),
          Card(
              child: Padding(
                  padding: EdgeInsets.all(12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text("الأسعار والفائدة", style: TextStyle(fontWeight: FontWeight.bold)),
                    Divider(),
                    _infoRow("السعر الرسمي", currency(contract!.officialPrice)),
                    _infoRow("السعر مع الفائدة", currency(contract!.totalPrice)),
                    _infoRow("إجمالي الفائدة", currency(interest)),
                    _infoRow("المقدم", currency(contract!.downPayment)),
                    _infoRow("القسط الشهري", currency(contract!.monthlyInstallment)),
                    _infoRow("المتبقي", currency(contract!.remainingAmount)),
                    _infoRow("مدة العقد", "${contract!.contractMonths} شهر"),
                    _infoRow("بداية العقد", fmtShortDate(contract!.startDate)),
                  ]))),

          SizedBox(height: 12),
          Text("سجل الدفعات", style: TextStyle(fontWeight: FontWeight.bold)),
          SizedBox(height: 8),

          // add payment fields (labels above)
          Text("المبلغ (د.ع)", style: TextStyle(fontWeight: FontWeight.bold)),
          SizedBox(height: 6),
          TextField(controller: amountCtl, keyboardType: TextInputType.number, decoration: InputDecoration(border: OutlineInputBorder())),
          SizedBox(height: 8),
          Text("الطريقة (نقدي/تحويل/...)", style: TextStyle(fontWeight: FontWeight.bold)),
          SizedBox(height: 6),
          TextField(controller: methodCtl, decoration: InputDecoration(border: OutlineInputBorder())),
          SizedBox(height: 8),
          Text("ملاحظة (اختياري)", style: TextStyle(fontWeight: FontWeight.bold)),
          SizedBox(height: 6),
          TextField(controller: noteCtl, decoration: InputDecoration(border: OutlineInputBorder())),
          SizedBox(height: 10),
          ElevatedButton.icon(onPressed: _addPayment, icon: Icon(Icons.add), label: Text("تسديد دفعة")),

          SizedBox(height: 12),
          ...payments.map((p) {
            return Card(
              child: ListTile(
                title: Text("${currency(p.amount)}"),
                subtitle: Text("${fmtDate(p.date)} • ${p.method} ${p.note.isNotEmpty ? '• ${p.note}' : ''}"),
                trailing: IconButton(icon: Icon(Icons.delete, color: Colors.red), onPressed: () => _deletePayment(p.id!, p.amount)),
              ),
            );
          }).toList(),
          if (payments.isEmpty) Card(child: Padding(padding: EdgeInsets.all(12), child: Text("لا توجد دفعات بعد."))),
          SizedBox(height: 40),
        ]),
      ),
    );
  }

  Widget _infoRow(String k, String v) => Padding(
        padding: EdgeInsets.symmetric(vertical: 6),
        child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(k, style: TextStyle(color: Colors.grey[700])), Text(v, style: TextStyle(fontWeight: FontWeight.bold))]),
      );
}

/* ===========================
   Monthly Report Screen
   =========================== */
class MonthlyReportScreen extends StatefulWidget {
  final Future<List<Contract>>? contractsListFuture;
  final int? year;
  final int? month;
  MonthlyReportScreen({this.contractsListFuture, this.year, this.month});

  @override
  _MonthlyReportScreenState createState() => _MonthlyReportScreenState();
}

class _MonthlyReportScreenState extends State<MonthlyReportScreen> {
  Map<String, int> summary = {};
  bool loading = true;
  int year = DateTime.now().year;
  int month = DateTime.now().month;

  @override
  void initState() {
    super.initState();
    if (widget.year != null) year = widget.year!;
    if (widget.month != null) month = widget.month!;
    _load();
  }

  Future<void> _load() async {
    setState(() => loading = true);
    summary = await DBHelper.instance.monthlySummary(year: year, month: month);
    setState(() => loading = false);
  }

  // copy summary as text to clipboard
  void _copySummary() {
    final txt = """
تقرير شهري - ${year}-${month.toString().padLeft(2,'0')}
المجموع المقسَط: ${currency(summary['totalGranted'] ?? 0)}
المستلم هذا الشهر: ${currency(summary['totalReceived'] ?? 0)}
المتبقي: ${currency(summary['totalRemaining'] ?? 0)}
الأرباح المتوقعة: ${currency(summary['expectedProfit'] ?? 0)}
المتوقع هذا الشهر: ${currency(summary['expectedMonthly'] ?? 0)}
""";
    Clipboard.setData(ClipboardData(text: txt));
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("تم نسخ التقرير إلى الحافظة")));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("تقرير شهري"),
        actions: [IconButton(icon: Icon(Icons.copy), onPressed: _copySummary)],
      ),
      body: loading
          ? Center(child: CircularProgressIndicator())
          : Padding(
              padding: EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text("التقرير لشهر ${month.toString().padLeft(2, '0')} - $year", style: TextStyle(fontWeight: FontWeight.bold)),
                SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: EdgeInsets.all(12),
                    child: Column(children: [
                      _infoRow("المجموع المقسَط", currency(summary['totalGranted'] ?? 0)),
                      _infoRow("المستلم هذا الشهر", currency(summary['totalReceived'] ?? 0)),
                      _infoRow("المتبقي", currency(summary['totalRemaining'] ?? 0)),
                      _infoRow("الأرباح المتوقعة", currency(summary['expectedProfit'] ?? 0)),
                      _infoRow("المتوقع هذا الشهر", currency(summary['expectedMonthly'] ?? 0)),
                    ]),
                  ),
                ),
                SizedBox(height: 12),
                Text("ملاحظة: هذا تقرير مبدئي استناداً للبيانات المحفوظة محلياً.", style: TextStyle(fontSize: 12, color: Colors.grey[700])),
              ]),
            ),
    );
  }

  Widget _infoRow(String k, String v) => Padding(
        padding: EdgeInsets.symmetric(vertical: 6),
        child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(k), Text(v, style: TextStyle(fontWeight: FontWeight.bold))]),
      );
}

/* ===========================
   Search delegate (optional)
   =========================== */
class ContractSearchDelegate extends SearchDelegate<String> {
  final List<Contract> list;
  ContractSearchDelegate(this.list);

  @override
  String get searchFieldLabel => "ابحث بالاسم، رقم العقد، أو الهاتف";

  @override
  List<Widget>? buildActions(BuildContext context) => [IconButton(icon: Icon(Icons.clear), onPressed: () => query = "")];

  @override
  Widget? buildLeading(BuildContext context) => IconButton(icon: Icon(Icons.arrow_back), onPressed: () => close(context, ""));

  @override
  Widget buildResults(BuildContext context) {
    final q = query.toLowerCase();
    final results = list.where((c) => c.customerName.toLowerCase().contains(q) || (c.id?.toString() ?? "").contains(q) || c.phoneNumber.contains(q)).toList();
    return ListView(children: results.map((c) => ListTile(title: Text(c.customerName), subtitle: Text(c.phoneNumber))).toList());
  }

  @override
  Widget buildSuggestions(BuildContext context) {
    final q = query.toLowerCase();
    final results = list.where((c) => c.customerName.toLowerCase().contains(q) || (c.id?.toString() ?? "").contains(q) || c.phoneNumber.contains(q)).toList();
    return ListView(children: results.map((c) => ListTile(title: Text(c.customerName), subtitle: Text(c.phoneNumber))).toList());
  }
}
