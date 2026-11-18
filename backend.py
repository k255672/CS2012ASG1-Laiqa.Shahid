"""
FinPay - Transaction Manager (backend)
CS2012 Assignment 1

All the logic lives here. main.py only draws the window and calls the
FinPayEngine class at the bottom of this file.

Quick check without the UI:  python backend.py sample_transactions.csv
"""

import csv
import json
import math
import os
from abc import ABC, abstractmethod
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_FILE = os.path.join(BASE_DIR, "exported_transactions.csv")
AUDIT_FILE = os.path.join(BASE_DIR, "audit_log.txt")

NO_FILTER = (None, None, None, None)


class FinPayError(Exception):
    """Parent of all the errors this program raises on purpose."""


class InvalidTransactionError(FinPayError):
    """A single transaction breaks a rule (for example amount <= 0)."""


class FileLoadError(FinPayError):
    """The whole file could not be used (missing, broken, wrong type...)."""


class ExportError(FinPayError):
    """Exporting the csv / audit log failed."""


class Transaction(ABC):
    """Base class for one wallet transaction."""

    def __init__(self, city, date, time, amount, status):
        self.city = city
        self.date = date
        self.time = time
        self.amount = amount
        self.status = status

    @property
    def city(self):
        return self._city

    @city.setter
    def city(self, value):
        if not isinstance(value, str) or value.strip() == "":
            raise InvalidTransactionError("city cannot be empty")
        self._city = value.strip()

    @property
    def date(self):
        return self._date

    @date.setter
    def date(self, value):
        try:
            parsed = datetime.strptime(str(value).strip(), "%Y-%m-%d")
        except ValueError:
            raise InvalidTransactionError(f"invalid date (expected YYYY-MM-DD): {value}")
        self._date = parsed.strftime("%Y-%m-%d")

    @property
    def time(self):
        return self._time

    @time.setter
    def time(self, value):
        text = str(value).strip()
        for pattern in ("%H:%M:%S", "%H:%M"):
            try:
                parsed = datetime.strptime(text, pattern)
            except ValueError:
                continue
            self._time = parsed.strftime("%H:%M:%S")
            return
        raise InvalidTransactionError(f"invalid time (expected HH:MM:SS): {value}")

    @property
    def amount(self):
        return self._amount

    @amount.setter
    def amount(self, value):
        if isinstance(value, bool):
            raise InvalidTransactionError(f"invalid amount: {value}")
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            raise InvalidTransactionError(f"amount is not a number: {value}")
        # nan and inf would slip past a plain <= 0 check
        if not math.isfinite(number):
            raise InvalidTransactionError(f"amount is not a real number: {value}")
        if number <= 0:
            raise InvalidTransactionError(f"amount must be greater than 0, got {number}")
        self._amount = number

  
    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        if not isinstance(value, str) or value.strip() == "":
            raise InvalidTransactionError("status cannot be empty")
        self._status = value.strip().title()

    @abstractmethod
    def get_net_impact(self) -> float:
        """How much this transaction changes the wallet balance."""

    @abstractmethod
    def get_type(self) -> str:
        """'Credit' or 'Debit' (shown in the Type column)."""

    def to_dict(self):
        return {
            "City": self._city,
            "Date": self._date,
            "Time": self._time,
            "Type": self.get_type(),
            "Amount": f"{self._amount:.2f}",
            "Status": self._status,
        }

    def __str__(self):
        return (f"{self.get_type()} | {self._city} | {self._date} {self._time} | "
                f"{self._amount:.2f} | {self._status}")


class CreditTransaction(Transaction):
    def __init__(self, city, date, time, amount, status):
        super().__init__(city, date, time, amount, status)

    def get_net_impact(self) -> float:
        return self.amount

    def get_type(self) -> str:
        return "Credit"


class DebitTransaction(Transaction):
    def __init__(self, city, date, time, amount, status):
        super().__init__(city, date, time, amount, status)

    def get_net_impact(self) -> float:
        return -self.amount

    def get_type(self) -> str:
        return "Debit"



class FileLoader(ABC):
    """Base class for the csv / json readers."""

    @abstractmethod
    def parse_file(self, filepath: str) -> list[Transaction]:
        """Read a file and return only the valid transactions."""

    @abstractmethod
    def read_rows(self, filepath: str) -> list:
        """Get the raw rows out of the file without checking them."""

    def build_transaction(self, row) -> Transaction:
        """Turn one raw row (a dict) into a Credit/Debit transaction.

        Raises InvalidTransactionError if the row is bad.
        """
        if not isinstance(row, dict):
            raise InvalidTransactionError(f"row is not a record: {row}")
        if None in row:
            raise InvalidTransactionError("row has more values than columns")

        data = {}
        for key, value in row.items():
            data[str(key).strip().lower()] = value

        kind = str(data.get("type", "")).strip().lower()
        fields = (data.get("city"), data.get("date"), data.get("time"),
                  data.get("amount"), data.get("status"))

        if kind == "credit":
            return CreditTransaction(*fields)
        if kind == "debit":
            return DebitTransaction(*fields)
        raise InvalidTransactionError(f"unknown transaction type: '{kind}'")


class CSVLoader(FileLoader):

    def read_rows(self, filepath: str) -> list:
        rows = []
        try:
            # utf-8-sig removes the invisible mark that Excel puts at the start
            with open(filepath, newline="", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
        except FileNotFoundError:
            raise FileLoadError(f"File not found: {filepath}")
        except csv.Error as error:
            raise FileLoadError(f"The CSV file is damaged: {error}")
        except OSError as error:
            raise FileLoadError(f"Could not open the file: {error}")
        return rows

    def parse_file(self, filepath: str) -> list[Transaction]:
        transactions = []
        for row in self.read_rows(filepath):
            try:
                transactions.append(self.build_transaction(row))
            except (InvalidTransactionError, KeyError, ValueError, TypeError):
                continue  # corrupted row, skip it
        return transactions


class JSONLoader(FileLoader):

    def read_rows(self, filepath: str) -> list:
        try:
            with open(filepath, encoding="utf-8-sig", errors="replace") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise FileLoadError(f"File not found: {filepath}")
        except json.JSONDecodeError as error:
            raise FileLoadError(
                f"Invalid JSON on line {error.lineno}, column {error.colno}: {error.msg}")
        except OSError as error:
            raise FileLoadError(f"Could not open the file: {error}")

        # the top level can be a plain list or an object that holds the list
        if isinstance(data, dict):
            rows = data.get("transactions")
            if rows is None:
                for value in data.values():
                    if isinstance(value, list):
                        rows = value
                        break
        else:
            rows = data

        if not isinstance(rows, list):
            raise FileLoadError("Unexpected JSON structure: could not find a list of transactions.")
        return rows

    def parse_file(self, filepath: str) -> list[Transaction]:
        transactions = []
        for row in self.read_rows(filepath):
            try:
                transactions.append(self.build_transaction(row))
            except (InvalidTransactionError, KeyError, ValueError, TypeError):
                continue  # corrupted record, skip it
        return transactions




class IngestionQueue:
    """FIFO queue that holds the raw rows before they are validated."""

    def __init__(self):
        self._items = []
        self._front = 0  

    def enqueue(self, item):
        self._items.append(item)

    def dequeue(self):
        if self.is_empty():
            raise IndexError("dequeue from an empty queue")
        item = self._items[self._front]
        self._front += 1
        if self._front == len(self._items):
            self._items = []
            self._front = 0
        return item

    def is_empty(self):
        return self._front >= len(self._items)

    def size(self):
        return len(self._items) - self._front


class FilterHistoryStack:
    """LIFO stack that remembers the earlier filter states (for undo)."""

    def __init__(self):
        self._items = []

    def push(self, state):
        self._items.append(state)

    def pop(self):
        if self.is_empty():
            raise IndexError("pop from an empty stack")
        return self._items.pop()

    def peek(self):
        if self.is_empty():
            raise IndexError("peek at an empty stack")
        return self._items[-1]

    def is_empty(self):
        return len(self._items) == 0

    def size(self):
        return len(self._items)


class AuditNode:
    """One node of the audit linked list. Holds a 4-element tuple."""

    def __init__(self, record):
        if not isinstance(record, tuple) or len(record) != 4:
            raise ValueError("an audit record must be a tuple with 4 elements")
        self.record = record  # (timestamp, action_type, record_count, net_amount)
        self.next = None


class ExportAuditLinkedList:
    """Singly linked list of AuditNode objects (oldest first)."""

    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0

    def append(self, record):
        node = AuditNode(record)
        if self.head is None:
            self.head = node
            self.tail = node
        else:
            self.tail.next = node
            self.tail = node
        self.size += 1

    def traverse(self) -> list[str]:
        """Walk the list from head to tail and build one text line per node."""
        lines = []
        current = self.head
        number = 1
        while current is not None:
            timestamp, action_type, record_count, net_amount = current.record
            lines.append(f"{number:>3}. [{timestamp}]  {action_type:<7}  "
                         f"records: {record_count:<6}  net amount: {net_amount:+,.2f}")
            current = current.next
            number += 1
        return lines



class FinPayEngine:

    def __init__(self):
        self.loaders = {".csv": CSVLoader(), ".json": JSONLoader()}
        self.ingestion_queue = IngestionQueue()

        self.transactions = []          # active store: every valid transaction that was loaded
        self.visible_transactions = []  # what the table currently shows (after filters)

        self.unique_cities: set[str] = set()
        self.unique_dates: set[str] = set()
        self.unique_times: set[str] = set()

        self.filter_history = FilterHistoryStack()
        self.current_filter = NO_FILTER

        self.audit_log = ExportAuditLinkedList()

    # ----- loading -----

    def get_loader(self, filepath):
        extension = os.path.splitext(filepath)[1].lower()
        loader = self.loaders.get(extension)
        if loader is None:
            raise FileLoadError(f"Unsupported file type '{extension}'. Please choose a .csv or .json file.")
        return loader

    def load_data(self, filepath):
        """Load a file. Returns (records_loaded, rows_skipped)."""
        loader = self.get_loader(filepath)
        raw_rows = loader.read_rows(filepath)

        
        self.ingestion_queue = IngestionQueue()
        for row in raw_rows:
            self.ingestion_queue.enqueue(row)

        loaded = []
        skipped = 0
        while not self.ingestion_queue.is_empty():
            row = self.ingestion_queue.dequeue()
            try:
                loaded.append(loader.build_transaction(row))
            except (InvalidTransactionError, KeyError, ValueError, TypeError):
                skipped += 1

        if len(loaded) == 0:
            raise FileLoadError(
                "No valid transactions were found in this file.\n"
                "Please check that it has the columns: city, date, time, type, amount, status.")

        
        self.transactions = loaded
        self._collect_unique_values()
        self.filter_history = FilterHistoryStack()
        self.current_filter = NO_FILTER
        self.visible_transactions = list(self.transactions)

        self._log_action("LOAD", self.transactions)
        return len(loaded), skipped

    def _collect_unique_values(self):
        self.unique_cities = set()
        self.unique_dates = set()
        self.unique_times = set()
        for transaction in self.transactions:
            self.unique_cities.add(transaction.city)
            self.unique_dates.add(transaction.date)
            self.unique_times.add(transaction.time)

    

    def apply_filters(self, city=None, date=None, time=None, kind=None):
        # remember where we were before changing anything
        self.filter_history.push(self.current_filter)
        self.current_filter = (city, date, time, kind)
        self._refresh_visible()
        self._log_action("FILTER", self.visible_transactions)

    def revert_last_filter(self):
        """Go back one filter. Returns False if there is nothing to go back to."""
        if self.filter_history.is_empty():
            return False
        self.current_filter = self.filter_history.pop()
        self._refresh_visible()
        return True

    def clear_filters(self):
        # pop everything off the stack, the oldest state is the unfiltered view
        while not self.filter_history.is_empty():
            self.filter_history.pop()
        self.current_filter = NO_FILTER
        self._refresh_visible()

    def _refresh_visible(self):
        city, date, time, kind = self.current_filter
        result = []
        for transaction in self.transactions:
            if city is not None and transaction.city != city:
                continue
            if date is not None and transaction.date != date:
                continue
            if time is not None and transaction.time != time:
                continue
            if kind is not None and transaction.get_type() != kind:
                continue
            result.append(transaction)
        self.visible_transactions = result

   

    def export_data(self):
        """Write the filtered rows to exported_transactions.csv and the audit log to audit_log.txt."""
        if len(self.visible_transactions) == 0:
            raise ExportError("There are no records to export.")

        fieldnames = ["City", "Date", "Time", "Type", "Amount", "Status"]
        try:
            with open(EXPORT_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for transaction in self.visible_transactions:
                    writer.writerow(transaction.to_dict())
        except OSError as error:
            raise ExportError(f"Could not write exported_transactions.csv "
                              f"(is it open in another program?)\n{error}")

        # log the export first so it also shows up inside audit_log.txt
        self._log_action("EXPORT", self.visible_transactions)
        self._write_audit_file()
        return EXPORT_FILE, AUDIT_FILE

    def _log_action(self, action_type, records):
        net_amount = 0.0
        for transaction in records:
            net_amount += transaction.get_net_impact()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # a tuple, so the record can't be changed after it is stored
        self.audit_log.append((timestamp, action_type, len(records), round(net_amount, 2)))

    def _write_audit_file(self):
        lines = self.audit_log.traverse()
        try:
            with open(AUDIT_FILE, "w", encoding="utf-8") as f:
                f.write("FinPay Audit Log\n")
                f.write("Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
                f.write("-" * 78 + "\n")
                for line in lines:
                    f.write(line + "\n")
        except OSError as error:
            raise ExportError(f"Could not write audit_log.txt:\n{error}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: python backend.py <file.csv or file.json>")
    else:
        engine = FinPayEngine()
        try:
            found = engine.get_loader(sys.argv[1]).parse_file(sys.argv[1])
            print(f"{len(found)} valid transactions in {sys.argv[1]}")
            for item in found:
                print("  ", item)
        except FinPayError as error:
            print("Error:", error)
