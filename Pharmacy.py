import tkinter as tk
from tkinter import ttk, messagebox
import pyodbc
from datetime import datetime, timedelta
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use('TkAgg')

def format_vnd(amount):
    try:
        return f"{float(amount):,.0f} ₫"
    except (ValueError, TypeError):
        return amount

class LoginWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("ĐĂNG NHẬP HỆ THỐNG NHÀ THUỐC")
        self.root.geometry("400x300")
        self.root.resizable(False, False)

        self.conn = pyodbc.connect(
            "Driver={SQL Server};"
            "Server=localhost;"
            "Database=PharmacyDB;"
            "Trusted_Connection=yes;"
        )
        self.cursor = self.conn.cursor()

        self.var_username = tk.StringVar()
        self.var_password = tk.StringVar()

        self.setup_ui()

    def setup_ui(self):
        lbl_title = tk.Label(self.root, text="HỆ THỐNG ĐĂNG NHẬP", font=("Arial", 16, "bold"), bg="#2c3e50", fg="white", pady=10)
        lbl_title.pack(fill=tk.X)

        form_frame = tk.Frame(self.root, pady=20)
        form_frame.pack()

        tk.Label(form_frame, text="Tài khoản:", font=("Arial", 11)).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        tk.Entry(form_frame, textvariable=self.var_username, font=("Arial", 11), width=20).grid(row=0, column=1, padx=10, pady=10)

        tk.Label(form_frame, text="Mật khẩu:", font=("Arial", 11)).grid(row=1, column=0, padx=10, pady=10, sticky="w")
        tk.Entry(form_frame, textvariable=self.var_password, show="*", font=("Arial", 11), width=20).grid(row=1, column=1, padx=10, pady=10)

        btn_login = tk.Button(self.root, text="Đăng Nhập", command=self.login, bg="#16a085", fg="white", font=("Arial", 11, "bold"), width=15, pady=5)
        btn_login.pack(pady=10)

    def login(self):
        u = self.var_username.get()
        p = self.var_password.get()

        if u == "" or p == "":
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập đầy đủ tài khoản và mật khẩu!")
            return

        self.cursor.execute("SELECT Role FROM Users WHERE Username = ? AND Password = ?", (u, p))
        row = self.cursor.fetchone()

        if row:
            role = row[0]
            messagebox.showinfo("Thành công", f"Đăng nhập thành công với quyền: {role}")
            self.root.destroy()
            main_root = tk.Tk()
            app = AdvancedPharmacySystem(main_root, role, u)
            main_root.mainloop()
        else:
            messagebox.showerror("Thất bại", "Tài khoản hoặc mật khẩu không chính xác!")


class AdvancedPharmacySystem:
    def __init__(self, root, role, current_user):
        self.root = root
        self.role = role
        self.current_user = current_user

        self.root.title(f"Hệ Thống Quản Lý Nhà Thuốc - [{self.role} Mode]")
        self.root.geometry("1280x750")
        self.root.state('zoomed')

        self.conn = pyodbc.connect(
            "Driver={SQL Server};"
            "Server=localhost;"
            "Database=PharmacyDB;"
            "Trusted_Connection=yes;"
        )
        self.cursor = self.conn.cursor()

        self.cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='ImportHistory' AND xtype='U')
            CREATE TABLE ImportHistory (
                ImportID   INT IDENTITY(1,1) PRIMARY KEY,
                ProductID  INT,
                Quantity   INT,
                ImportPrice FLOAT,
                TotalCost  FLOAT,
                ImportDate DATETIME DEFAULT GETDATE()
            )
        """)
        self.conn.commit()

        self.var_id = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_cat = tk.StringVar()
        self.var_uses = tk.StringVar()
        self.var_price = tk.DoubleVar()
        self.var_import_price = tk.DoubleVar()
        self.var_stock = tk.IntVar()
        self.var_expiry = tk.StringVar()
        self.var_search = tk.StringVar()

        self.var_sell_qty = tk.IntVar(value=1)
        self.var_import_qty = tk.IntVar(value=10)

        self.cart_items = []

        self.setup_ui()
        self.fetch_data()
        self.apply_permissions()

    def setup_ui(self):
        lbl_title = tk.Label(self.root, text=f"💊 PHARMACY ECOSYSTEM | Tài khoản: {self.current_user} ({self.role})",
                             font=("Arial", 20, "bold"), bg="#2c3e50" if self.role == "Admin" else "#2980b9",
                             fg="white", pady=12)
        lbl_title.pack(side=tk.TOP, fill=tk.X)

        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=1, padx=10, pady=10)

        self.left_frame = tk.LabelFrame(main_frame, text=" BẢNG ĐIỀU KHIỂN CHI TIẾT ", font=("Arial", 11, "bold"),
                                        fg="#2c3e50", bd=3, relief=tk.RIDGE, width=420)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        self.left_frame.pack_propagate(False)

        fields = [
            ("Tên thuốc:", self.var_name),
            ("Danh mục:", self.var_cat),
            ("Công dụng dễ nhớ:", self.var_uses),
            ("Giá bán (VNĐ):", self.var_price),
            ("Giá nhập (VNĐ):", self.var_import_price),
            ("Tồn kho hiện tại:", self.var_stock),
            ("Hạn dùng (YYYY-MM-DD):", self.var_expiry)
        ]

        for i, (label, var) in enumerate(fields):
            tk.Label(self.left_frame, text=label, font=("Arial", 10)).grid(row=i, column=0, padx=10, pady=6, sticky="w")
            tk.Entry(self.left_frame, textvariable=var, font=("Arial", 10), bd=2, width=24).grid(row=i, column=1, padx=10, pady=6)

        self.lbl_price_display = tk.Label(self.left_frame, text="", font=("Arial", 9, "italic"), fg="#16a085")
        self.lbl_price_display.grid(row=3, column=2, padx=4, sticky="w")

        self.lbl_import_display = tk.Label(self.left_frame, text="", font=("Arial", 9, "italic"), fg="#8e44ad")
        self.lbl_import_display.grid(row=4, column=2, padx=4, sticky="w")

        self.var_price.trace_add("write", lambda *_: self.lbl_price_display.config(text=format_vnd(self._safe_get(self.var_price))))
        self.var_import_price.trace_add("write", lambda *_: self.lbl_import_display.config(text=format_vnd(self._safe_get(self.var_import_price))))

        self.crud_btn_frame = tk.LabelFrame(self.left_frame, text="Thao tác dữ liệu", font=("Arial", 9, "italic"), fg="red")
        self.crud_btn_frame.grid(row=7, column=0, columnspan=2, pady=10, padx=10, sticky="we")

        self.btn_add = tk.Button(self.crud_btn_frame, text="Thêm Mới", command=self.add_item, bg="#2ecc71", fg="white", width=9)
        self.btn_add.grid(row=0, column=0, padx=4, pady=5)
        self.btn_update = tk.Button(self.crud_btn_frame, text="Cập Nhật", command=self.update_item, bg="#3498db", fg="white", width=9)
        self.btn_update.grid(row=0, column=1, padx=4, pady=5)
        self.btn_delete = tk.Button(self.crud_btn_frame, text="Xóa Thuốc", command=self.delete_item, bg="#e74c3c", fg="white", width=9)
        self.btn_delete.grid(row=0, column=2, padx=4, pady=5)
        tk.Button(self.crud_btn_frame, text="Xóa Trắng", command=self.clear_fields, bg="#95a5a6", fg="white", width=9).grid(row=0, column=3, padx=4, pady=5)

        #Giỏ hàng
        self.sell_frame = tk.LabelFrame(self.left_frame, text=" GIỎ HÀNG - BÁN NHIỀU LOẠI ", font=("Arial", 10, "bold"), fg="#d35400", bd=2)
        self.sell_frame.grid(row=8, column=0, columnspan=2, pady=10, padx=10, sticky="we")

        tk.Label(self.sell_frame, text="Số lượng:").grid(row=0, column=0, padx=6, pady=4)
        tk.Entry(self.sell_frame, textvariable=self.var_sell_qty, width=7, font=("Arial", 10)).grid(row=0, column=1, padx=4)
        tk.Button(self.sell_frame, text="➕ Thêm vào giỏ", command=self.add_to_cart, bg="#e67e22", fg="white", font=("Arial", 9, "bold")).grid(row=0, column=2, padx=6, pady=4)

        cart_cols = ("Tên thuốc", "SL", "Đơn giá", "Thành tiền")
        self.cart_table = ttk.Treeview(self.sell_frame, columns=cart_cols, show="headings", height=4)
        self.cart_table.heading("Tên thuốc", text="Tên thuốc")
        self.cart_table.heading("SL", text="SL")
        self.cart_table.heading("Đơn giá", text="Đơn giá")
        self.cart_table.heading("Thành tiền", text="Thành tiền")
        self.cart_table.column("Tên thuốc", width=120)
        self.cart_table.column("SL", width=35, anchor="center")
        self.cart_table.column("Đơn giá", width=88, anchor="e")
        self.cart_table.column("Thành tiền", width=90, anchor="e")
        self.cart_table.grid(row=1, column=0, columnspan=3, padx=6, pady=4, sticky="we")

        self.lbl_sell_total = tk.Label(self.sell_frame, text="Tổng giỏ hàng: 0 ₫", font=("Arial", 10, "bold"), fg="#d35400")
        self.lbl_sell_total.grid(row=2, column=0, columnspan=2, padx=6, pady=2, sticky="w")

        tk.Button(self.sell_frame, text="🗑 Xóa dòng", command=self.remove_cart_item, bg="#95a5a6", fg="white", font=("Arial", 9)).grid(row=2, column=2, padx=6, pady=2)
        tk.Button(self.sell_frame, text="💰 THANH TOÁN", command=self.checkout_cart, bg="#c0392b", fg="white", font=("Arial", 10, "bold")).grid(row=3, column=0, columnspan=3, padx=6, pady=6, sticky="we")

        self.var_sell_qty.trace_add("write", lambda *_: self._update_sell_total())
        self.var_price.trace_add("write", lambda *_: self._update_sell_total())

        #Nhập hàng
        self.import_frame = tk.LabelFrame(self.left_frame, text=" NHẬP HÀNG THÊM ", font=("Arial", 10, "bold"), fg="#27ae60", bd=2)
        self.import_frame.grid(row=9, column=0, columnspan=2, pady=5, padx=10, sticky="we")

        tk.Label(self.import_frame, text="Số lượng nhập:").grid(row=0, column=0, padx=10, pady=5)
        tk.Entry(self.import_frame, textvariable=self.var_import_qty, width=8, font=("Arial", 10)).grid(row=0, column=1, padx=5)
        self.btn_import = tk.Button(self.import_frame, text="➕ NHẬP KHO", command=self.import_stock, bg="#27ae60", fg="white", font=("Arial", 10, "bold"))
        self.btn_import.grid(row=0, column=2, padx=10, pady=5)

        #Thống kê
        self.stat_frame = tk.LabelFrame(self.left_frame, text=" BÁO CÁO THỐNG KÊ ", font=("Arial", 10, "bold"), fg="#8e44ad", bd=2)
        self.stat_frame.grid(row=10, column=0, columnspan=2, pady=10, padx=10, sticky="we")

        self.btn_chart1 = tk.Button(self.stat_frame, text="Doanh Thu Tuần/Tháng", command=self.report_revenue, bg="#8e44ad", fg="white", width=18)
        self.btn_chart1.grid(row=0, column=0, padx=5, pady=5)
        self.btn_chart2 = tk.Button(self.stat_frame, text="Thuốc Bán Chạy Nhất", command=self.report_best_sellers, bg="#9b59b6", fg="white", width=18)
        self.btn_chart2.grid(row=0, column=1, padx=5, pady=5)

        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1, padx=5)

        #Quỹ + Bill
        fund_bar = tk.Frame(right_frame, bg="#27ae60")
        fund_bar.pack(fill=tk.X, pady=(0, 6))

        self.lbl_total_fund = tk.Label(
            fund_bar,
            text="🏦  TỔNG QUỸ CỬA HÀNG: đang tải...",
            font=("Arial", 16, "bold"),
            bg="#27ae60", fg="white",
            pady=10, padx=20, anchor="w"
        )
        self.lbl_total_fund.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        self.btn_view_bills = tk.Button(
            fund_bar,
            text="📋 XEM HÓA ĐƠN",
            command=self.show_bills_window,
            bg="#2c3e50", fg="white",
            font=("Arial", 11, "bold"),
            padx=14, pady=8, cursor="hand2"
        )
        self.btn_view_bills.pack(side=tk.RIGHT, padx=10, pady=6)

        #Tìm kiếm
        search_bar = tk.Frame(right_frame)
        search_bar.pack(fill=tk.X, pady=5)

        tk.Label(search_bar, text="Tìm kiếm (Tên/Công dụng):", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Entry(search_bar, textvariable=self.var_search, font=("Arial", 10), width=35).pack(side=tk.LEFT, padx=5)
        tk.Button(search_bar, text="Tìm kiếm", command=self.search_data, bg="#34495e", fg="white", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(search_bar, text="Hiển thị tất cả", command=self.fetch_data, bg="#7f8c8d", fg="white").pack(side=tk.LEFT, padx=5)

        note_frame = tk.Frame(right_frame)
        note_frame.pack(fill=tk.X)
        tk.Label(note_frame, text="⚠️ Chú thích trạng thái: ", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        tk.Label(note_frame, text=" Hết hạn / Hết hàng ", bg="#ffcccc", fg="red", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Label(note_frame, text=" Cận hạn (< 3 tháng) / Sắp hết hàng (<10) ", bg="#ffe6cc", fg="#d35400", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)

        self.table = ttk.Treeview(right_frame, columns=("ID", "Name", "Cat", "Uses", "Price", "ImportPrice", "Stock", "Expiry"))
        self.table.pack(fill=tk.BOTH, expand=1, pady=5)

        self.table.heading("ID", text="Mã")
        self.table.heading("Name", text="Tên Thuốc")
        self.table.heading("Cat", text="Danh Mục")
        self.table.heading("Uses", text="Công Dụng Dễ Nhớ")
        self.table.heading("Price", text="Giá Bán")
        self.table.heading("ImportPrice", text="Giá Nhập")
        self.table.heading("Stock", text="Tồn Kho")
        self.table.heading("Expiry", text="Hạn Sử Dụng")
        self.table['show'] = 'headings'

        self.table.column("ID", width=40, anchor="center")
        self.table.column("Name", width=130)
        self.table.column("Uses", width=180)
        self.table.column("Price", width=110, anchor="e")
        self.table.column("ImportPrice", width=110, anchor="e")
        self.table.column("Stock", width=60, anchor="center")
        self.table.column("Expiry", width=90, anchor="center")

        self.table.bind("<ButtonRelease-1>", self.get_cursor)
        self.table.tag_configure("CRITICAL", background="#ffcccc", foreground="#c0392b")
        self.table.tag_configure("WARNING", background="#ffe6cc", foreground="#d35400")
        self.table.tag_configure("NORMAL", background="white", foreground="black")

    #Bill

    def show_bills_window(self):
        """Mở cửa sổ xem danh sách hóa đơn"""
        win = tk.Toplevel(self.root)
        win.title("📋 Danh Sách Hóa Đơn")
        win.geometry("900x580")
        win.grab_set()  # Khóa focus vào cửa sổ này

        tk.Label(win, text="DANH SÁCH HÓA ĐƠN", font=("Arial", 15, "bold"),
                 bg="#2c3e50", fg="white", pady=10).pack(fill=tk.X)

        #Lọc
        filter_frame = tk.Frame(win, pady=6)
        filter_frame.pack(fill=tk.X, padx=10)

        tk.Label(filter_frame, text="Lọc theo ngày:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)

        self.var_bill_filter = tk.StringVar(value="all")
        filters = [("Tất cả", "all"), ("Hôm nay", "today"), ("7 ngày", "7days"), ("30 ngày", "30days")]
        for text, val in filters:
            tk.Radiobutton(filter_frame, text=text, variable=self.var_bill_filter, value=val,
                           command=lambda: self._load_bills(bill_tree, detail_tree, lbl_bill_total),
                           font=("Arial", 10)).pack(side=tk.LEFT, padx=8)

        #Ds Bill
        top_frame = tk.Frame(win)
        top_frame.pack(fill=tk.BOTH, expand=1, padx=10, pady=5)

        bill_cols = ("BillID", "Ngày giờ", "Tổng tiền")
        bill_tree = ttk.Treeview(top_frame, columns=bill_cols, show="headings", height=8)
        bill_tree.heading("BillID", text="Mã HĐ")
        bill_tree.heading("Ngày giờ", text="Ngày giờ xuất")
        bill_tree.heading("Tổng tiền", text="Tổng tiền")
        bill_tree.column("BillID", width=70, anchor="center")
        bill_tree.column("Ngày giờ", width=180, anchor="center")
        bill_tree.column("Tổng tiền", width=150, anchor="e")

        sb_bill = ttk.Scrollbar(top_frame, orient=tk.VERTICAL, command=bill_tree.yview)
        bill_tree.configure(yscrollcommand=sb_bill.set)
        bill_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        sb_bill.pack(side=tk.LEFT, fill=tk.Y)

        lbl_bill_total = tk.Label(win, text="Tổng cộng: 0 ₫  |  0 hóa đơn",
                                  font=("Arial", 11, "bold"), fg="#2c3e50", anchor="e")
        lbl_bill_total.pack(fill=tk.X, padx=15, pady=2)

        tk.Label(win, text="CHI TIẾT HÓA ĐƠN", font=("Arial", 10, "bold"),
                 bg="#34495e", fg="white", pady=4).pack(fill=tk.X, padx=0)

        #Chi tiết Bill
        bot_frame = tk.Frame(win)
        bot_frame.pack(fill=tk.BOTH, expand=1, padx=10, pady=5)

        detail_cols = ("Tên thuốc", "Số lượng", "Đơn giá", "Thành tiền")
        detail_tree = ttk.Treeview(bot_frame, columns=detail_cols, show="headings", height=6)
        detail_tree.heading("Tên thuốc", text="Tên thuốc")
        detail_tree.heading("Số lượng", text="Số lượng")
        detail_tree.heading("Đơn giá", text="Đơn giá")
        detail_tree.heading("Thành tiền", text="Thành tiền")
        detail_tree.column("Tên thuốc", width=250)
        detail_tree.column("Số lượng", width=80, anchor="center")
        detail_tree.column("Đơn giá", width=130, anchor="e")
        detail_tree.column("Thành tiền", width=150, anchor="e")

        sb_detail = ttk.Scrollbar(bot_frame, orient=tk.VERTICAL, command=detail_tree.yview)
        detail_tree.configure(yscrollcommand=sb_detail.set)
        detail_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        sb_detail.pack(side=tk.LEFT, fill=tk.Y)

        def on_bill_select(event):
            sel = bill_tree.focus()
            if not sel:
                return
            bill_id = bill_tree.item(sel)['values'][0]
            self._load_bill_details(detail_tree, bill_id)

        bill_tree.bind("<ButtonRelease-1>", on_bill_select)

        self._load_bills(bill_tree, detail_tree, lbl_bill_total)

    def _load_bills(self, bill_tree, detail_tree, lbl_total):
        """Tải danh sách hóa đơn theo bộ lọc"""
        bill_tree.delete(*bill_tree.get_children())
        detail_tree.delete(*detail_tree.get_children())

        f = self.var_bill_filter.get()
        if f == "today":
            where = "WHERE CAST(BillDate AS DATE) = CAST(GETDATE() AS DATE)"
        elif f == "7days":
            where = "WHERE BillDate >= DATEADD(day, -7, GETDATE())"
        elif f == "30days":
            where = "WHERE BillDate >= DATEADD(day, -30, GETDATE())"
        else:
            where = ""

        self.cursor.execute(f"SELECT BillID, BillDate, TotalAmount FROM Bills {where} ORDER BY BillDate DESC")
        rows = self.cursor.fetchall()

        total = 0
        for row in rows:
            bill_tree.insert('', tk.END, values=(
                row[0],
                str(row[1])[:19],
                format_vnd(row[2])
            ))
            total += row[2]

        lbl_total.config(text=f"Tổng cộng: {format_vnd(total)}  |  {len(rows)} hóa đơn")

    def _load_bill_details(self, detail_tree, bill_id):
        """Tải chi tiết các mặt hàng trong 1 hóa đơn"""
        detail_tree.delete(*detail_tree.get_children())
        self.cursor.execute("""
            SELECT P.DrugName, BD.Quantity, BD.Price, BD.Quantity * BD.Price
            FROM BillDetails BD
            JOIN Products P ON BD.ProductID = P.ID
            WHERE BD.BillID = ?
        """, (bill_id,))
        rows = self.cursor.fetchall()
        for row in rows:
            detail_tree.insert('', tk.END, values=(
                row[0],
                row[1],
                format_vnd(row[2]),
                format_vnd(row[3])
            ))

    def _safe_get(self, var):
        try:
            return var.get()
        except tk.TclError:
            return 0

    def _update_sell_total(self):
        total = sum(item['qty'] * item['price'] for item in self.cart_items)
        self.lbl_sell_total.config(text=f"Tổng giỏ hàng: {format_vnd(total)}")

    def _refresh_cart_table(self):
        self.cart_table.delete(*self.cart_table.get_children())
        for item in self.cart_items:
            self.cart_table.insert('', tk.END, values=(
                item['name'], item['qty'],
                format_vnd(item['price']),
                format_vnd(item['qty'] * item['price'])
            ))
        self._update_sell_total()

    def add_to_cart(self):
        if not self.var_id.get():
            messagebox.showwarning("Chưa chọn thuốc", "Vui lòng click chọn thuốc từ bảng danh sách trước!")
            return
        product_id = int(self.var_id.get())
        name = self.var_name.get()
        price = self.var_price.get()
        qty = self.var_sell_qty.get()
        stock = int(self.var_stock.get())

        if qty <= 0:
            messagebox.showerror("Lỗi", "Số lượng phải lớn hơn 0!")
            return

        for item in self.cart_items:
            if item['id'] == product_id:
                new_qty = item['qty'] + qty
                if new_qty > stock:
                    messagebox.showerror("Không đủ hàng", f"Kho chỉ còn {stock} sản phẩm, giỏ đã có {item['qty']}!")
                    return
                item['qty'] = new_qty
                self._refresh_cart_table()
                return

        if qty > stock:
            messagebox.showerror("Không đủ hàng", f"Kho chỉ còn {stock} sản phẩm!")
            return

        self.cart_items.append({'id': product_id, 'name': name, 'qty': qty, 'price': price, 'stock': stock})
        self._refresh_cart_table()

    def remove_cart_item(self):
        selected = self.cart_table.focus()
        if not selected:
            messagebox.showwarning("Chưa chọn", "Vui lòng click chọn dòng cần xóa trong giỏ hàng!")
            return
        idx = self.cart_table.index(selected)
        del self.cart_items[idx]
        self._refresh_cart_table()

    def checkout_cart(self):
        if not self.cart_items:
            messagebox.showwarning("Giỏ trống", "Vui lòng thêm ít nhất một loại thuốc vào giỏ hàng!")
            return

        total_bill = sum(item['qty'] * item['price'] for item in self.cart_items)

        try:
            self.cursor.execute("INSERT INTO Bills (BillDate, TotalAmount) VALUES (GETDATE(), ?)", (total_bill,))
            self.cursor.execute("SELECT @@IDENTITY")
            bill_id = self.cursor.fetchone()[0]

            lines = []
            for item in self.cart_items:
                self.cursor.execute("INSERT INTO BillDetails (BillID, ProductID, Quantity, Price) VALUES (?, ?, ?, ?)",
                                    (bill_id, item['id'], item['qty'], item['price']))
                self.cursor.execute("SELECT Stock FROM Products WHERE ID=?", (item['id'],))
                cur_stock = self.cursor.fetchone()[0]
                self.cursor.execute("UPDATE Products SET Stock=? WHERE ID=?", (cur_stock - item['qty'], item['id']))
                lines.append(f"  • {item['name']}: {item['qty']} x {format_vnd(item['price'])} = {format_vnd(item['qty']*item['price'])}")

            self.conn.commit()
            self.cart_items.clear()
            self._refresh_cart_table()
            self.fetch_data()

            sep = "-" * 42
            detail_text = "\n".join(lines)
            messagebox.showinfo("Thanh toán thành công",
                "Nhân viên: {}\nHóa đơn #{}\n{}\n{}\n{}\nTỔNG CỘNG: {}".format(
                    self.current_user, bill_id, sep, detail_text, sep, format_vnd(total_bill)))
        except Exception as e:
            self.conn.rollback()
            messagebox.showerror("Lỗi hệ thống", f"Giao dịch thất bại: {e}")

    def apply_permissions(self):
        if self.role == "Staff":
            self.btn_add.config(state=tk.DISABLED, bg="#bdc3c7")
            self.btn_update.config(state=tk.DISABLED, bg="#bdc3c7")
            self.btn_delete.config(state=tk.DISABLED, bg="#bdc3c7")
            self.btn_import.config(state=tk.DISABLED, bg="#bdc3c7")
            self.btn_chart1.config(state=tk.DISABLED, bg="#bdc3c7")
            self.btn_chart2.config(state=tk.DISABLED, bg="#bdc3c7")
            self.crud_btn_frame.config(text="Thao tác dữ liệu (Bị khóa)")
            self.import_frame.config(text="NHẬP HÀNG THÊM (Bị khóa)")
            self.stat_frame.config(text="BÁO CÁO THỐNG KÊ (Bị khóa)")

    #Data

    def update_total_fund(self):
        try:
            self.cursor.execute("SELECT ISNULL(SUM(TotalAmount), 0) FROM Bills")
            total_revenue = self.cursor.fetchone()[0]
            self.cursor.execute("SELECT ISNULL(SUM(TotalCost), 0) FROM ImportHistory")
            total_import = self.cursor.fetchone()[0]
            fund = total_revenue - total_import
            color = "#27ae60" if fund >= 0 else "#c0392b"
            self.lbl_total_fund.config(text=f"🏦  TỔNG QUỸ CỬA HÀNG: {format_vnd(fund)}", bg=color)
        except Exception:
            self.lbl_total_fund.config(text="🏦  TỔNG QUỸ CỬA HÀNG: 0 ₫", bg="#e67e22")

    def fetch_data(self):
        self.update_total_fund()
        self.cursor.execute("SELECT * FROM Products")
        rows = self.cursor.fetchall()
        self.table.delete(*self.table.get_children())

        now = datetime.now().date()
        three_months_later = now + timedelta(days=90)

        for row in rows:
            tag = "NORMAL"
            exp_date = row[7]
            stock = row[6]

            if exp_date:
                if isinstance(exp_date, str):
                    exp_date = datetime.strptime(exp_date, "%Y-%m-%d").date()
                if exp_date <= now or stock <= 0:
                    tag = "CRITICAL"
                elif exp_date <= three_months_later or stock <= 10:
                    tag = "WARNING"

            display_price = format_vnd(row[4])
            display_import_price = "******" if self.role == "Staff" else format_vnd(row[5])
            self.table.insert('', tk.END, values=(row[0], row[1], row[2], row[3], display_price,
                                                  display_import_price, row[6], str(row[7])), tags=(tag,))

    def get_cursor(self, ev):
        cursor_row = self.table.focus()
        contents = self.table.item(cursor_row)
        row = contents['values']
        if row:
            self.var_id.set(row[0])
            self.var_name.set(row[1])
            self.var_cat.set(row[2])
            self.var_uses.set(row[3])
            self._load_raw_price(row[0])
            self.var_stock.set(row[6])
            self.var_expiry.set(row[7])

    def _load_raw_price(self, product_id):
        self.cursor.execute("SELECT Price, ImportPrice FROM Products WHERE ID=?", (product_id,))
        price_row = self.cursor.fetchone()
        if price_row:
            self.var_price.set(price_row[0])
            if self.role != "Staff":
                self.var_import_price.set(price_row[1])

    def clear_fields(self):
        self.var_id.set("")
        self.var_name.set("")
        self.var_cat.set("")
        self.var_uses.set("")
        self.var_price.set(0.0)
        self.var_import_price.set(0.0)
        self.var_stock.set(0)
        self.var_expiry.set("")
        self.lbl_price_display.config(text="")
        self.lbl_import_display.config(text="")
        self.lbl_sell_total.config(text="Tổng giỏ hàng: 0 ₫")

    def add_item(self):
        if self.role != "Admin": return
        try:
            self.cursor.execute("INSERT INTO Products VALUES (?,?,?,?,?,?,?)",
                                (self.var_name.get(), self.var_cat.get(), self.var_uses.get(),
                                 self.var_price.get(), self.var_import_price.get(), self.var_stock.get(),
                                 self.var_expiry.get()))
            self.conn.commit()
            self.fetch_data()
            messagebox.showinfo("Thành công", "Đã thêm loại thuốc mới thành công!")
            self.clear_fields()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi định dạng nhập liệu!\nChi tiết: {e}")

    def update_item(self):
        if self.role != "Admin": return
        if not self.var_id.get():
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn một loại thuốc từ bảng!")
            return
        self.cursor.execute(
            "UPDATE Products SET DrugName=?, Category=?, Uses=?, Price=?, ImportPrice=?, Stock=?, ExpiryDate=? WHERE ID=?",
            (self.var_name.get(), self.var_cat.get(), self.var_uses.get(), self.var_price.get(),
             self.var_import_price.get(), self.var_stock.get(), self.var_expiry.get(), self.var_id.get()))
        self.conn.commit()
        self.fetch_data()
        messagebox.showinfo("Thành công", "Đã cập nhật thông tin thành công!")

    def delete_item(self):
        if self.role != "Admin": return
        if not self.var_id.get(): return
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa sản phẩm này?"):
            self.cursor.execute("DELETE FROM Products WHERE ID=?", (self.var_id.get(),))
            self.conn.commit()
            self.fetch_data()
            self.clear_fields()

    def search_data(self):
        query = self.var_search.get()
        self.cursor.execute("SELECT * FROM Products WHERE DrugName LIKE ? OR Uses LIKE ?", (f'%{query}%', f'%{query}%'))
        rows = self.cursor.fetchall()
        self.table.delete(*self.table.get_children())
        for row in rows:
            display_price = format_vnd(row[4])
            display_import_price = "******" if self.role == "Staff" else format_vnd(row[5])
            self.table.insert('', tk.END, values=(row[0], row[1], row[2], row[3], display_price,
                                                  display_import_price, row[6], str(row[7])), tags=("NORMAL",))

    def import_stock(self):
        if self.role != "Admin": return
        if not self.var_id.get(): return
        product_id = int(self.var_id.get())
        qty_to_import = self.var_import_qty.get()
        new_stock = int(self.var_stock.get()) + qty_to_import
        import_price = self.var_import_price.get()

        if qty_to_import <= 0: return

        total_cost = import_price * qty_to_import
        self.cursor.execute("UPDATE Products SET Stock = ? WHERE ID = ?", (new_stock, product_id))
        self.cursor.execute(
            "INSERT INTO ImportHistory (ProductID, Quantity, ImportPrice, TotalCost) VALUES (?, ?, ?, ?)",
            (product_id, qty_to_import, import_price, total_cost))
        self.conn.commit()
        self.fetch_data()
        messagebox.showinfo("Thành công", f"Đã nạp thêm {qty_to_import} đơn vị vào kho.\nChi phí nhập: {format_vnd(total_cost)}")

    def report_revenue(self):
        if self.role != "Admin": return
        self.cursor.execute("SELECT ISNULL(SUM(TotalAmount), 0) FROM Bills WHERE BillDate >= DATEADD(day, -7, GETDATE())")
        weekly_rev = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT ISNULL(SUM(TotalAmount), 0) FROM Bills WHERE BillDate >= DATEADD(day, -30, GETDATE())")
        monthly_rev = self.cursor.fetchone()[0]

        plt.figure(figsize=(7, 5))
        bars = plt.bar(['Doanh thu 7 ngày qua', 'Doanh thu 30 ngày qua'], [weekly_rev, monthly_rev],
                       color=['#3498db', '#2ecc71'], width=0.4)
        plt.title("BÁO CÁO DOANH THU HỆ THỐNG", fontsize=14, fontweight='bold')
        plt.ylabel("Số tiền (VNĐ)")
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2.0, yval, f"{yval:,.0f} ₫", va='bottom', ha='center', fontweight='bold')
        plt.tight_layout()
        plt.show()

    def report_best_sellers(self):
        if self.role != "Admin": return
        self.cursor.execute("""
            SELECT P.DrugName, SUM(BD.Quantity) as TotalSold FROM BillDetails BD
            JOIN Products P ON BD.ProductID = P.ID
            GROUP BY P.DrugName ORDER BY TotalSold DESC
        """)
        data = self.cursor.fetchall()
        if not data: return
        names = [row[0] for row in data]
        sold_qty = [row[1] for row in data]
        plt.figure(figsize=(10, 5))
        plt.barh(names[::-1], sold_qty[::-1], color='#e67e22')
        plt.title("DANH SÁCH THUỐC TIÊU THỤ MẠNH", fontsize=13, fontweight='bold')
        plt.xlabel("Số lượng bán (Đơn vị)")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    login_root = tk.Tk()
    login_app = LoginWindow(login_root)
    login_root.mainloop()
