import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from tkcalendar import DateEntry
import pandas as pd
import os

DB_FILE = 'debts.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('Alacak','Borç')),
            amount REAL NOT NULL,
            FOREIGN KEY(person_id) REFERENCES persons(id)
        )
    ''')
    conn.commit()
    conn.close()

class DebtApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Borç Hesaplama Uygulaması")
        self.geometry("1000x600")
        init_db()
        self.tree_items = {}
        self.create_widgets()
        self.refresh_persons()
        self.show_transactions()

    def create_widgets(self):
        # Sol panel
        left_frame = ttk.LabelFrame(self, text="Kişiler")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)

        new_person_btn = ttk.Button(left_frame, text="Yeni Kişi Ekle", 
                                    command=self.open_person_dialog)
        new_person_btn.pack(fill=tk.X, padx=5, pady=(5,2))

        delete_person_btn = ttk.Button(left_frame, text="Kişi Sil", 
                                       command=self.delete_person)
        delete_person_btn.pack(fill=tk.X, padx=5, pady=(2,5))
        export_btn = ttk.Button(left_frame, text="Excel Oluştur", 
                                command=self.export_to_excel)
        export_btn.pack(fill=tk.X, padx=5, pady=(2,5))

        # Kişi listesi
        self.name_listbox = tk.Listbox(left_frame, width=25)
        self.name_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=(10,5))
        self.name_listbox.bind('<<ListboxSelect>>', self.on_name_select)
        self.name_listbox.bind('<Button-1>', self.on_listbox_click)
        self.name_listbox.bind('<Button-3>', self.show_name_context_menu)


        self.name_menu = tk.Menu(self, tearoff=0)
        self.name_menu.add_command(label="Alacak Ekle", command=lambda: self.open_transaction_dialog('Alacak'))
        self.name_menu.add_command(label="Borç Ekle", command=lambda: self.open_transaction_dialog('Borç'))

        # Sağ panel
        right_frame = ttk.LabelFrame(self, text="İşlemler")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=5)

        cols = ('No','Kişi','Tarih','Tür','Tutar')
        self.tree = ttk.Treeview(right_frame, columns=cols, show='headings')
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor='center', width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind('<Button-1>', self.on_tree_click)
        self.tree.bind('<Button-3>', self.show_context_menu)

        # İşlem silme menüsü
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Sil", command=self.delete_transaction)

        self.total_label = ttk.Label(right_frame, text="Toplam Alacak: 0 | Toplam Borç: 0 | Bakiye: 0")
        self.total_label.pack(pady=(0,10))
    
    def export_to_excel(self):
        sel = self.name_listbox.curselection()
        now = datetime.now().strftime("%Y%m%d_%H%M%S")

        if not sel:
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("""
                SELECT p.name AS Kişi, t.date AS Tarih, t.type AS Tür, t.amount AS Tutar
                FROM transactions t
                JOIN persons p ON t.person_id = p.id
                ORDER BY p.name, date(t.date, 'dd.MM.yyyy')
            """)
            rows = c.fetchall()
            conn.close()

            if not rows:
                messagebox.showinfo("Bilgi", "Henüz hiçbir işlem kaydedilmemiş.")
                return

           
            df_all = pd.DataFrame(rows, columns=['Kişi','Tarih','Tür','Tutar'])

            summary = df_all.pivot_table(
                index='Kişi',
                columns='Tür',
                values='Tutar',
                aggfunc='sum',
                fill_value=0
            ).reset_index()
            summary.columns.name = None
            summary['Bakiye'] = summary.get('Alacak', 0) - summary.get('Borç', 0)

            filename = f"tüm_islemler_{now}.xlsx"

            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                summary.to_excel(writer, sheet_name='Özet', index=False)
                df_all.to_excel(writer, sheet_name='Tüm İşlemler', index=False)

            messagebox.showinfo(
                "Başarılı",
                f"Tüm işlemler ve özet Excel dosyası oluşturuldu:\n{os.path.abspath(filename)}"
            )
            return

        name = self.name_listbox.get(sel[0])
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            """
            SELECT t.date AS Tarih, t.type AS Tür, t.amount AS Tutar
            FROM transactions t
            JOIN persons p ON t.person_id = p.id
            WHERE p.name = ?
            ORDER BY date(t.date, 'dd.MM.yyyy')
            """,
            (name,)
        )
        rows = c.fetchall()
        conn.close()

        if not rows:
            messagebox.showinfo("Bilgi", f"{name} için kayıtlı işlem bulunamadı.")
            return

        df = pd.DataFrame(rows, columns=['Tarih','Tür','Tutar'])
        toplam_alacak = df.loc[df['Tür']=='Alacak','Tutar'].sum()
        toplam_borc   = df.loc[df['Tür']=='Borç','Tutar'].sum()
        bakiye        = toplam_alacak - toplam_borc

        filename = f"{name.replace(' ','_')}_islemler_{now}.xlsx"

        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            sheet = 'İşlemler'
            df.to_excel(writer, sheet_name=sheet, index=False, startrow=4)
            ws = writer.sheets[sheet]
            ws.cell(row=1, column=1, value='Kişi:')
            ws.cell(row=1, column=2, value=name)
            ws.cell(row=2, column=1, value='Toplam Alacak:')
            ws.cell(row=2, column=2, value=toplam_alacak)
            ws.cell(row=3, column=1, value='Toplam Borç:')
            ws.cell(row=3, column=2, value=toplam_borc)
            ws.cell(row=4, column=1, value='Bakiye:')
            ws.cell(row=4, column=2, value=bakiye)

        messagebox.showinfo(
            "Başarılı",
            f"Excel dosyası oluşturuldu:\n{os.path.abspath(filename)}"
        )
  

    def refresh_persons(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, name FROM persons ORDER BY name")
        self.persons = c.fetchall()
        conn.close()

        self.name_listbox.delete(0, tk.END)
        for _, name in self.persons:
            self.name_listbox.insert(tk.END, name)

    def on_listbox_click(self, event):
        idx = self.name_listbox.nearest(event.y)
        if idx >= self.name_listbox.size():
            self.name_listbox.selection_clear(0, tk.END)
            self.show_transactions()

    def on_tree_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            self.name_listbox.selection_clear(0, tk.END)
            self.show_transactions()

    def show_name_context_menu(self, event):
        idx = self.name_listbox.nearest(event.y)
        if idx < self.name_listbox.size():
            self.name_listbox.selection_clear(0, tk.END)
            self.name_listbox.selection_set(idx)
            self.name_menu.tk_popup(event.x_root, event.y_root)

    def open_person_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Yeni Kişi ve İşlem Ekle")
        dialog.grab_set()

        ttk.Label(dialog, text="İsim:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        name_entry = ttk.Entry(dialog)
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Tarih:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
        date_entry = DateEntry(dialog, date_pattern='dd.MM.yyyy')
        date_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Tür:").grid(row=2, column=0, padx=5, pady=5, sticky='e')
        type_cb = ttk.Combobox(dialog, values=['Alacak','Borç'], state='readonly')
        type_cb.grid(row=2, column=1, padx=5, pady=5)
        type_cb.current(0)

        ttk.Label(dialog, text="Tutar:").grid(row=3, column=0, padx=5, pady=5, sticky='e')
        amount_entry = ttk.Entry(dialog)
        amount_entry.grid(row=3, column=1, padx=5, pady=5)

        def save_person():
            name = name_entry.get().strip()
            date_str = date_entry.get()
            t_type = type_cb.get()
            amount_str = amount_entry.get().strip()
            if not (name and date_str and amount_str):
                messagebox.showwarning("Uyarı", "Tüm alanları doldurun.", parent=dialog)
                return
            try:
                datetime.strptime(date_str, '%d.%m.%Y')
                amount = float(amount_str)
            except Exception as e:
                messagebox.showerror("Hata", f"Tarih veya tutar hatalı:\n{e}", parent=dialog)
                return
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT id FROM persons WHERE name = ?", (name,))
            res = c.fetchone()
            if res:
                if not messagebox.askyesno("Uyarı", "Bu kişi zaten kayıtlı. İşlem eklemek istediğinize emin misiniz?", parent=dialog):
                    conn.close()
                    return
                pid = res[0]
            else:
                c.execute("INSERT INTO persons (name) VALUES (?)", (name,))
                pid = c.lastrowid
            c.execute(
                "INSERT INTO transactions (person_id, date, type, amount) VALUES (?,?,?,?)",
                (pid, date_str, t_type, amount)
            )
            conn.commit()
            conn.close()
            dialog.destroy()
            self.refresh_persons()
            self.name_listbox.selection_set([i for i,(pid,n) in enumerate(self.persons) if n==name][0])
            self.show_transactions(name)

        save_btn = ttk.Button(dialog, text="Kaydet", command=save_person)
        save_btn.grid(row=4, column=0, columnspan=2, pady=10)

    def open_transaction_dialog(self, default_type):
        sel = self.name_listbox.curselection()
        if not sel:
            return
        name = self.name_listbox.get(sel[0])
        dialog = tk.Toplevel(self)
        dialog.title(f"{name} için {default_type} Ekle")
        dialog.grab_set()

        ttk.Label(dialog, text="Tarih:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        date_entry = DateEntry(dialog, date_pattern='dd.MM.yyyy')
        date_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Tutar:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
        amount_entry = ttk.Entry(dialog)
        amount_entry.grid(row=1, column=1, padx=5, pady=5)

        def save_transaction():
            date_str = date_entry.get()
            amount_str = amount_entry.get().strip()
            if not (date_str and amount_str):
                messagebox.showwarning("Uyarı", "Tüm alanları doldurun.", parent=dialog)
                return
            try:
                datetime.strptime(date_str, '%d.%m.%Y')
                amount = float(amount_str)
            except Exception as e:
                messagebox.showerror("Hata", f"Tarih veya tutar hatalı:\n{e}", parent=dialog)
                return
            pid = next((pid for pid, n in self.persons if n == name), None)
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(
                "INSERT INTO transactions (person_id, date, type, amount) VALUES (?,?,?,?)",
                (pid, date_str, default_type, amount)
            )
            conn.commit()
            conn.close()
            dialog.destroy()
            self.show_transactions(name)

        save_btn = ttk.Button(dialog, text="Kaydet", command=save_transaction)
        save_btn.grid(row=2, column=0, columnspan=2, pady=10)

    def delete_person(self):
        sel = self.name_listbox.curselection()
        if not sel:
            return
        name = self.name_listbox.get(sel[0])
        if messagebox.askyesno("Kişi Silme Onayı", f"{name} ve tüm işlemleri silinsin mi?" ):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM transactions WHERE person_id = (SELECT id FROM persons WHERE name = ?)", (name,))
            c.execute("DELETE FROM persons WHERE name = ?", (name,))
            conn.commit()
            conn.close()
            self.refresh_persons()
            self.show_transactions()

    def on_name_select(self, event):
        sel = self.name_listbox.curselection()
        if sel:
            self.show_transactions(self.name_listbox.get(sel[0]))

    def show_transactions(self, name=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree_items.clear()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        if name:
            c.execute(
                "SELECT t.id, p.name, t.date, t.type, t.amount FROM transactions t"
                " JOIN persons p ON t.person_id = p.id"
                " WHERE p.name = ?"
                " ORDER BY date(t.date, 'dd.MM.yyyy')",
                (name,)
            )
        else:
            c.execute(
                "SELECT t.id, p.name, t.date, t.type, t.amount FROM transactions t"
                " JOIN persons p ON t.person_id = p.id"
                " ORDER BY p.name, date(t.date, 'dd.MM.yyyy')"
            )
        rows = c.fetchall()
        toplam_alacak = toplam_borc = 0
        for idx, (tid, person, date, t_type, amount) in enumerate(rows, start=1):
            iid = self.tree.insert('', tk.END, values=(idx, person, date, t_type, amount))
            self.tree_items[iid] = tid
            if t_type == 'Alacak':
                toplam_alacak += amount
            else:
                toplam_borc += amount
        conn.close()
        bakiye = toplam_alacak - toplam_borc
        self.total_label.config(
            text=f"Toplam Alacak: {toplam_alacak} | Toplam Borç: {toplam_borc} | Bakiye: {bakiye}"
        )

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.menu.tk_popup(event.x_root, event.y_root)

    def delete_transaction(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        tid = self.tree_items.get(iid)
        if not tid:
            return
        if messagebox.askyesno("Silme Onayı", "Bu işlemi silmek istediğinize emin misiniz?" ):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM transactions WHERE id = ?", (tid,))
            conn.commit()
            conn.close()
            sel_list = self.name_listbox.curselection()
            name = self.name_listbox.get(sel_list[0]) if sel_list else None
            self.show_transactions(name)

if __name__ == '__main__':
    app = DebtApp()
    app.mainloop()
