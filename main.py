"""
مدير الميزانية الشخصية (Personal Budget Manager)
تطبيق Flet + SQLite لإدارة الدخل والمصاريف الشخصية.

التشغيل على الكمبيوتر:
    pip install flet
    flet run main.py

بناء APK للأندرويد:
    flet build apk
"""

import sqlite3
import flet as ft

# --------------------------------------------------------------------------
# إعدادات عامة وثوابت
# --------------------------------------------------------------------------

DB_NAME = "budget.db"

CAT_ESSENTIAL = "أساسي / ضروري"
CAT_LUXURY = "كمالي / ثانوي"

BG_COLOR = "#0E1A2B"
CARD_BG = "#16233A"
FIELD_BG = "#1C2C46"

INCOME_COLOR = ft.Colors.BLUE_400
EXPENSE_COLOR = ft.Colors.ORANGE_400
POSITIVE_COLOR = ft.Colors.GREEN_400
NEGATIVE_COLOR = ft.Colors.RED_400
SUGGESTION_COLOR = ft.Colors.AMBER_400


# --------------------------------------------------------------------------
# طبقة قاعدة البيانات (SQLite)
# --------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """يفتح اتصالاً جديداً بقاعدة بيانات SQLite المحلية."""
    return sqlite3.connect(DB_NAME)


def init_db() -> None:
    """ينشئ الجداول المطلوبة إن لم تكن موجودة، ويضبط الدخل الافتراضي."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            income REAL NOT NULL DEFAULT 0
        )
        """
    )
    cur.execute("INSERT OR IGNORE INTO settings (id, income) VALUES (1, 0)")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def db_get_income() -> float:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT income FROM settings WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row else 0.0


def db_set_income(value: float) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE settings SET income = ? WHERE id = 1", (value,))
    conn.commit()
    conn.close()


def db_add_expense(name: str, amount: float, category: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO expenses (name, amount, category) VALUES (?, ?, ?)",
        (name, amount, category),
    )
    conn.commit()
    conn.close()


def db_delete_expense(expense_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()


def db_clear_expenses() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses")
    conn.commit()
    conn.close()


def db_get_expenses() -> list[tuple[int, str, float, str]]:
    """يعيد المصاريف مرتّبة: الأساسي/الضروري أولاً ثم الكمالي/الثانوي."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, amount, category
        FROM expenses
        ORDER BY CASE WHEN category = ? THEN 0 ELSE 1 END, id ASC
        """,
        (CAT_ESSENTIAL,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# --------------------------------------------------------------------------
# دوال مساعدة
# --------------------------------------------------------------------------

def parse_amount(text: str, allow_zero: bool = True) -> float | None:
    """يحاول تحويل النص إلى رقم عشري صحيح؛ يعيد None عند الفشل."""
    if text is None:
        return None
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        return None
    if allow_zero:
        if value < 0:
            return None
    else:
        if value <= 0:
            return None
    return value


def fmt(value: float) -> str:
    return f"{value:.2f}"


# --------------------------------------------------------------------------
# التطبيق
# --------------------------------------------------------------------------

def main(page: ft.Page) -> None:
    page.title = "مدير الميزانية الشخصية"
    page.rtl = True
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG_COLOR
    page.padding = 0
    page.window.width = 420
    page.window.height = 860
    page.scroll = ft.ScrollMode.HIDDEN

    init_db()

    # ---------------------------------------------------------------
    # عناصر ملخص الميزانية (3 بطاقات)
    # ---------------------------------------------------------------

    income_value_text = ft.Text("0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    expenses_value_text = ft.Text("0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    remaining_value_text = ft.Text("0.00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)

    def summary_card(title: str, value_control: ft.Text, color: str, icon: str) -> ft.Container:
        return ft.Container(
            expand=True,
            padding=14,
            border_radius=16,
            bgcolor=ft.Colors.with_opacity(0.12, color),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
                controls=[
                    ft.Icon(icon, color=color, size=20),
                    ft.Text(title, size=12, color=color, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
                    value_control,
                ],
            ),
        )

    income_card = summary_card("الدخل", income_value_text, INCOME_COLOR, ft.Icons.PAYMENTS_OUTLINED)
    expenses_card = summary_card("إجمالي المصاريف", expenses_value_text, EXPENSE_COLOR, ft.Icons.SHOPPING_BAG_OUTLINED)
    remaining_card = summary_card("المتبقي", remaining_value_text, POSITIVE_COLOR, ft.Icons.SAVINGS_OUTLINED)

    summary_row = ft.Row(
        controls=[income_card, expenses_card, remaining_card],
        spacing=10,
    )

    # ---------------------------------------------------------------
    # قسم إدخال الدخل
    # ---------------------------------------------------------------

    income_field = ft.TextField(
        label="الدخل الشهري / الراتب",
        value=fmt(db_get_income()),
        keyboard_type=ft.KeyboardType.NUMBER,
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
        cursor_color=ft.Colors.WHITE,
    )

    def show_message(message: str, color: str) -> None:
        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(message, color=ft.Colors.WHITE),
                bgcolor=color,
            )
        )

    def handle_save_income(e: ft.Event) -> None:
        value = parse_amount(income_field.value, allow_zero=True)
        if value is None:
            show_message("⚠️ الرجاء إدخال رقم صحيح للدخل.", NEGATIVE_COLOR)
            return
        db_set_income(value)
        income_field.value = fmt(value)
        refresh_ui()
        show_message("✅ تم حفظ الدخل بنجاح.", POSITIVE_COLOR)

    save_income_button = ft.Button(
        content="حفظ / تحديث الدخل",
        icon=ft.Icons.SAVE_OUTLINED,
        on_click=handle_save_income,
        style=ft.ButtonStyle(
            bgcolor=INCOME_COLOR,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    income_section = ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=CARD_BG,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text("أدخل الدخل الشهري", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                income_field,
                save_income_button,
            ],
        ),
    )

    # ---------------------------------------------------------------
    # قسم إضافة مصروف
    # ---------------------------------------------------------------

    expense_name_field = ft.TextField(
        label="اسم المصروف",
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
        cursor_color=ft.Colors.WHITE,
    )

    expense_amount_field = ft.TextField(
        label="القيمة",
        keyboard_type=ft.KeyboardType.NUMBER,
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
        cursor_color=ft.Colors.WHITE,
    )

    expense_category_dropdown = ft.Dropdown(
        label="التصنيف",
        value=CAT_ESSENTIAL,
        options=[
            ft.DropdownOption(key=CAT_ESSENTIAL, text=CAT_ESSENTIAL),
            ft.DropdownOption(key=CAT_LUXURY, text=CAT_LUXURY),
        ],
        bgcolor=FIELD_BG,
        border_radius=10,
        color=ft.Colors.WHITE,
    )

    def handle_add_expense(e: ft.Event) -> None:
        name = (expense_name_field.value or "").strip()
        amount = parse_amount(expense_amount_field.value, allow_zero=False)
        category = expense_category_dropdown.value

        if not name:
            show_message("⚠️ الرجاء إدخال اسم المصروف.", NEGATIVE_COLOR)
            return
        if amount is None:
            show_message("⚠️ الرجاء إدخال قيمة رقمية موجبة صحيحة.", NEGATIVE_COLOR)
            return
        if category not in (CAT_ESSENTIAL, CAT_LUXURY):
            show_message("⚠️ الرجاء اختيار تصنيف المصروف.", NEGATIVE_COLOR)
            return

        db_add_expense(name, amount, category)

        expense_name_field.value = ""
        expense_amount_field.value = ""
        expense_category_dropdown.value = CAT_ESSENTIAL

        refresh_ui()
        show_message("✅ تمت إضافة المصروف بنجاح.", POSITIVE_COLOR)

    add_expense_button = ft.Button(
        content="➕ إضافة المصروف",
        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
        on_click=handle_add_expense,
        style=ft.ButtonStyle(
            bgcolor=EXPENSE_COLOR,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    add_expense_section = ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=CARD_BG,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text("أضف مصروفاً", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                expense_name_field,
                expense_amount_field,
                expense_category_dropdown,
                add_expense_button,
            ],
        ),
    )

    # ---------------------------------------------------------------
    # قسم قائمة المصاريف
    # ---------------------------------------------------------------

    expenses_list_column = ft.Column(spacing=8)

    def handle_delete_expense(expense_id: int) -> None:
        db_delete_expense(expense_id)
        refresh_ui()
        show_message("🗑️ تم حذف المصروف.", ft.Colors.BLUE_GREY_400)

    def build_expense_row(expense_id: int, name: str, amount: float, category: str) -> ft.Container:
        is_essential = category == CAT_ESSENTIAL
        tag_color = ft.Colors.TEAL_300 if is_essential else SUGGESTION_COLOR

        return ft.Container(
            padding=12,
            border_radius=12,
            bgcolor=FIELD_BG,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        spacing=4,
                        expand=True,
                        controls=[
                            ft.Text(name, size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                border_radius=20,
                                bgcolor=ft.Colors.with_opacity(0.18, tag_color),
                                content=ft.Text(category, size=11, color=tag_color, weight=ft.FontWeight.W_600),
                            ),
                        ],
                    ),
                    ft.Text(fmt(amount), size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=NEGATIVE_COLOR,
                        tooltip="حذف",
                        on_click=lambda e, eid=expense_id: handle_delete_expense(eid),
                    ),
                ],
            ),
        )

    empty_expenses_text = ft.Text(
        "لا توجد مصاريف مسجّلة بعد.",
        size=13,
        color=ft.Colors.BLUE_GREY_300,
        text_align=ft.TextAlign.CENTER,
    )

    def handle_clear_all_confirmed(e: ft.Event) -> None:
        db_clear_expenses()
        page.pop_dialog()
        refresh_ui()
        show_message("🗑️ تم مسح جميع المصاريف.", ft.Colors.BLUE_GREY_400)

    def handle_clear_all_cancelled(e: ft.Event) -> None:
        page.pop_dialog()

    def handle_clear_all_click(e: ft.Event) -> None:
        # يُبنى الحوار من جديد في كل مرة لتفادي إعادة استخدام نفس الكائن
        # قبل أن تكتمل دورة إغلاقه في الواجهة.
        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("تأكيد المسح"),
            content=ft.Text("هل أنت متأكد من مسح جميع المصاريف؟ لا يمكن التراجع عن هذا الإجراء."),
            actions=[
                ft.Button(
                    content="نعم، امسح الكل",
                    on_click=handle_clear_all_confirmed,
                    style=ft.ButtonStyle(bgcolor=NEGATIVE_COLOR, color=ft.Colors.WHITE),
                ),
                ft.OutlinedButton(content="إلغاء", on_click=handle_clear_all_cancelled),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(confirm_dialog)

    clear_all_button = ft.Button(
        content="مسح كل المصاريف",
        icon=ft.Icons.DELETE_SWEEP_OUTLINED,
        on_click=handle_clear_all_click,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.with_opacity(0.15, NEGATIVE_COLOR),
            color=NEGATIVE_COLOR,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    expenses_section = ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=CARD_BG,
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Text("المصاريف مرتبة حسب الأولوية", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                expenses_list_column,
                clear_all_button,
            ],
        ),
    )

    # ---------------------------------------------------------------
    # شريط التوصية الذكية
    # ---------------------------------------------------------------

    suggestion_text = ft.Text(
        "",
        size=13,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_600,
    )

    suggestion_bar = ft.Container(
        padding=14,
        border_radius=14,
        bgcolor=ft.Colors.with_opacity(0.15, SUGGESTION_COLOR),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, color=SUGGESTION_COLOR),
                ft.Container(content=suggestion_text, expand=True),
            ],
        ),
    )

    # ---------------------------------------------------------------
    # منطق تحديث الواجهة بالكامل
    # ---------------------------------------------------------------

    def refresh_ui() -> None:
        income = db_get_income()
        expenses = db_get_expenses()
        total_expenses = sum(row[2] for row in expenses)
        remaining = income - total_expenses

        income_value_text.value = fmt(income)
        expenses_value_text.value = fmt(total_expenses)
        remaining_value_text.value = fmt(remaining)

        if remaining >= 0:
            remaining_value_text.color = ft.Colors.WHITE
            remaining_card.bgcolor = ft.Colors.with_opacity(0.12, POSITIVE_COLOR)
            remaining_card.content.controls[0].color = POSITIVE_COLOR
            remaining_card.content.controls[1].color = POSITIVE_COLOR
        else:
            remaining_card.bgcolor = ft.Colors.with_opacity(0.12, NEGATIVE_COLOR)
            remaining_card.content.controls[0].color = NEGATIVE_COLOR
            remaining_card.content.controls[1].color = NEGATIVE_COLOR

        expenses_list_column.controls.clear()
        if expenses:
            for expense_id, name, amount, category in expenses:
                expenses_list_column.controls.append(
                    build_expense_row(expense_id, name, amount, category)
                )
        else:
            expenses_list_column.controls.append(empty_expenses_text)

        luxury_expenses = [row for row in expenses if row[3] == CAT_LUXURY]
        if luxury_expenses:
            biggest = max(luxury_expenses, key=lambda row: row[2])
            suggestion_text.value = (
                f"راجع «{biggest[1]}» لأنها أكبر مصروف كمالي (بقيمة {fmt(biggest[2])} دينار)."
            )
        elif remaining < 0:
            suggestion_text.value = "مصاريفك تجاوزت دخلك، راجع البنود الأساسية لتقليل العجز."
        else:
            suggestion_text.value = "لا توجد مصاريف كمالية حالياً، استمر في هذا الأداء الرائع للادخار!"

        page.update()

    # ---------------------------------------------------------------
    # تركيب الواجهة النهائية
    # ---------------------------------------------------------------

    header = ft.Container(
        padding=ft.Padding.only(top=20, bottom=10, left=20, right=20),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, color=INCOME_COLOR, size=28),
                ft.Text("مدير الميزانية الشخصية", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            ],
        ),
    )

    body = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=16,
        controls=[
            header,
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=20),
                content=ft.Column(
                    spacing=16,
                    controls=[
                        summary_row,
                        income_section,
                        add_expense_section,
                        expenses_section,
                        suggestion_bar,
                        ft.Container(height=20),
                    ],
                ),
            ),
        ],
    )

    page.add(ft.SafeArea(expand=True, content=body))

    refresh_ui()


ft.run(main)