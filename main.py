"""
FinPay - Transaction Manager (user interface)
CS2012 Assignment 1

Run with:  python main.py
backend.py must be in the same folder.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from backend import FinPayEngine, FinPayError

BG = "#f0f0f0"
ACCENT = "#2b5278"

ALL_CITIES = "All cities"
ALL_DATES = "All dates"
ALL_TIMES = "All times"
ALL_TYPES = "All"


class FinPayApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("FinPay - Transaction Manager")
        self.geometry("1040x640")
        self.minsize(1000, 560)
        self.configure(bg=BG)

        self.engine = FinPayEngine()
        self.chosen_file = ""

        self.setup_styles()

        # status bar at the bottom, shared by all three screens
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief="sunken",
                               anchor="w", padding=(8, 3))
        status_bar.pack(side="bottom", fill="x")

        # the three screens sit on top of each other, we just raise the one we need
        container = ttk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.welcome_screen = ttk.Frame(container)
        self.load_screen = ttk.Frame(container)
        self.dashboard_screen = ttk.Frame(container)
        for screen in (self.welcome_screen, self.load_screen, self.dashboard_screen):
            screen.grid(row=0, column=0, sticky="nsew")

        self.build_welcome()
        self.build_load()
        self.build_dashboard()

        self.show_welcome()


    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG)
        style.configure("Accent.TButton", background=ACCENT, foreground="white",
                        padding=(16, 5))
        style.map("Accent.TButton", background=[("active", "#3b6a99")])
        style.map("TEntry", fieldbackground=[("readonly", "white")])
        style.map("TCombobox", fieldbackground=[("readonly", "white")])
        style.configure("Treeview", rowheight=24, fieldbackground="white")
        style.configure("Treeview.Heading", background="#e4e4e4", font=("Arial", 9, "bold"))

    def set_status(self, text):
        self.status_var.set(text)



    def build_welcome(self):
        holder = ttk.Frame(self.welcome_screen)
        holder.place(relx=0.5, rely=0.45, anchor="center")

        ttk.Label(holder, text="Welcome to FinPay - Transaction Manager Software",
                  font=("Arial", 14, "bold")).pack()
        ttk.Label(holder, text="Internal Finance Department Portal",
                  font=("Arial", 9)).pack(pady=(6, 16))
        ttk.Button(holder, text="Get Started", style="Accent.TButton",
                   command=self.show_load).pack()

    def show_welcome(self):
        self.welcome_screen.tkraise()
        self.set_status("Ready")


    def build_load(self):
        self.load_screen.columnconfigure(0, weight=1)

        ttk.Label(self.load_screen, text="Load Transaction Data",
                  font=("Arial", 16, "bold")).grid(row=0, column=0, sticky="w",
                                                   padx=20, pady=(20, 12))

        box = ttk.LabelFrame(self.load_screen, text="Transaction file", padding=12)
        box.grid(row=1, column=0, sticky="ew", padx=20)
        box.columnconfigure(0, weight=1)

        ttk.Label(box, text="Browse to select a file. Supported formats: .csv, .json only."
                  ).grid(row=0, column=0, sticky="w")

        self.file_var = tk.StringVar(value="No file selected.")
        ttk.Entry(box, textvariable=self.file_var, state="readonly").grid(
            row=1, column=0, sticky="ew", pady=10)

        buttons = ttk.Frame(box)
        buttons.grid(row=2, column=0, sticky="w")
        ttk.Button(buttons, text="Browse File", command=self.browse_file).pack(side="left")
        self.load_button = ttk.Button(buttons, text="Load Data", command=self.load_data,
                                      state="disabled")
        self.load_button.pack(side="left", padx=8)

    def show_load(self):
        self.load_screen.tkraise()
        if self.chosen_file:
            self.set_status("File selected: " + os.path.basename(self.chosen_file))
        else:
            self.set_status("Waiting for file selection")

    def browse_file(self):
        path = filedialog.askopenfilename(
            title="Choose a transaction file",
            filetypes=[("CSV or JSON files", "*.csv *.json"),
                       ("CSV files", "*.csv"),
                       ("JSON files", "*.json")],
        )
        if not path:  # empty string = the user pressed Cancel
            return
        self.chosen_file = path
        self.file_var.set(path)
        self.load_button.config(state="normal")
        self.set_status("File selected: " + os.path.basename(path))

    def load_data(self):
        try:
            loaded, skipped = self.engine.load_data(self.chosen_file)
        except FinPayError as error:
            messagebox.showerror("Could not load file", str(error))
            self.set_status("Load failed - please choose another file")
            return

        self.fill_dropdowns()
        self.refresh_table()
        self.show_dashboard()

        if skipped > 0:
            messagebox.showwarning(
                "Some rows were skipped",
                f"{loaded} records were loaded.\n"
                f"{skipped} rows were skipped because they were corrupted or invalid.")


    def build_dashboard(self):
        screen = self.dashboard_screen
        screen.columnconfigure(0, weight=1)
        screen.rowconfigure(2, weight=1)

        ttk.Label(screen, text="Transaction Dashboard",
                  font=("Arial", 16, "bold")).grid(row=0, column=0, sticky="w",
                                                   padx=20, pady=(20, 8))


        bar = ttk.Frame(screen)
        bar.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        self.city_var = tk.StringVar(value=ALL_CITIES)
        self.date_var = tk.StringVar(value=ALL_DATES)
        self.time_var = tk.StringVar(value=ALL_TIMES)
        self.type_var = tk.StringVar(value=ALL_TYPES)

        ttk.Label(bar, text="Filter by:").grid(row=1, column=0, padx=(0, 8))
        self.city_box = self.make_filter(bar, 1, "City", self.city_var, 12)
        self.date_box = self.make_filter(bar, 2, "Date", self.date_var, 12)
        self.time_box = self.make_filter(bar, 3, "Time", self.time_var, 10)
        self.type_box = self.make_filter(bar, 4, "Type", self.type_var, 8)
        self.type_box["values"] = [ALL_TYPES, "Credit", "Debit"]

        ttk.Button(bar, text="Apply Filters", command=self.apply_filters).grid(
            row=1, column=5, padx=(10, 0))
        ttk.Button(bar, text="Clear Filters", command=self.clear_filters).grid(
            row=1, column=6, padx=(6, 0))
        ttk.Button(bar, text="Revert Last Filter", command=self.revert_filter).grid(
            row=1, column=7, padx=(6, 0))

    
        table_frame = ttk.Frame(screen)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=20)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        columns = ("city", "date", "time", "type", "amount", "status")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings",
                                  selectmode="browse")
        titles = {"city": "City", "date": "Date", "time": "Time",
                  "type": "Type", "amount": "Amount", "status": "Status"}
        widths = {"city": 170, "date": 120, "time": 110, "type": 100,
                  "amount": 130, "status": 120}
        for name in columns:
            alignment = "e" if name == "amount" else "w"
            self.table.heading(name, text=titles[name], anchor=alignment)
            self.table.column(name, width=widths[name], anchor=alignment)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        
        footer = ttk.Frame(screen)
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
        footer.columnconfigure(0, weight=1)
        ttk.Button(footer, text="Load Another File", command=self.show_load).grid(
            row=0, column=1, padx=(0, 8))
        ttk.Button(footer, text="Export", command=self.export_data).grid(row=0, column=2)

    def make_filter(self, parent, column, label, variable, width):
        ttk.Label(parent, text=label).grid(row=0, column=column, sticky="w", padx=(0, 6))
        box = ttk.Combobox(parent, textvariable=variable, state="readonly", width=width)
        box.grid(row=1, column=column, padx=(0, 6))
        return box

    def show_dashboard(self):
        self.dashboard_screen.tkraise()
        self.update_count_text()

    def fill_dropdowns(self):
        """Fill the dropdowns using the unique sets from the engine."""
        self.city_box["values"] = [ALL_CITIES] + sorted(self.engine.unique_cities)
        self.date_box["values"] = [ALL_DATES] + sorted(self.engine.unique_dates)
        self.time_box["values"] = [ALL_TIMES] + sorted(self.engine.unique_times)
        self.show_filter_state()

    def show_filter_state(self):
        """Make the dropdowns match the engine's current filter."""
        city, date, time, kind = self.engine.current_filter
        self.city_var.set(city if city is not None else ALL_CITIES)
        self.date_var.set(date if date is not None else ALL_DATES)
        self.time_var.set(time if time is not None else ALL_TIMES)
        self.type_var.set(kind if kind is not None else ALL_TYPES)

    def refresh_table(self):
        self.table.delete(*self.table.get_children())
        for transaction in self.engine.visible_transactions:
            self.table.insert("", "end", values=(
                transaction.city,
                transaction.date,
                transaction.time,
                transaction.get_type(),
                f"${transaction.amount:,.2f}",
                transaction.status,
            ))
        self.update_count_text()

    def update_count_text(self):
        total = len(self.engine.transactions)
        shown = len(self.engine.visible_transactions)
        text = f"Total Records Loaded: {total}"
        if shown != total:
            text += f"    |    Showing: {shown}"
        self.set_status(text)


    def apply_filters(self):
        city = self.city_var.get()
        date = self.date_var.get()
        time = self.time_var.get()
        kind = self.type_var.get()

        # turn the "All ..." texts back into None (= no filter)
        city = None if city == ALL_CITIES else city
        date = None if date == ALL_DATES else date
        time = None if time == ALL_TIMES else time
        kind = None if kind == ALL_TYPES else kind

        self.engine.apply_filters(city, date, time, kind)
        self.refresh_table()

    def revert_filter(self):
        if not self.engine.revert_last_filter():
            messagebox.showinfo("Revert Last Filter", "There is no earlier filter to go back to.")
            return
        self.show_filter_state()
        self.refresh_table()

    def clear_filters(self):
        self.engine.clear_filters()
        self.show_filter_state()
        self.refresh_table()

    def export_data(self):
        count = len(self.engine.visible_transactions)
        try:
            csv_path, log_path = self.engine.export_data()
        except FinPayError as error:
            messagebox.showerror("Export failed", str(error))
            return
        messagebox.showinfo(
            "Export complete",
            f"{count} records saved to:\n{csv_path}\n\nAudit log saved to:\n{log_path}")


if __name__ == "__main__":
    app = FinPayApp()
    app.mainloop()
