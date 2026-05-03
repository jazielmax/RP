###########################################################################################
# Daniel, David, Ben (Ident-FM)
# CSC 363
# frontend.py
# Last modified: May 4, 2026
# purpose: frontend to be used in 363 project. created using qt creator and pyside6.
###########################################################################################

# imports
import sys
import json
import urllib.request
from PySide6.QtWidgets import QApplication, QMainWindow, QHeaderView, QAbstractItemView
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import (QFile, QTimer, QTime, Qt, QEvent, QSortFilterProxyModel, QThread, Signal)
from PySide6.QtGui import QStandardItemModel, QStandardItem

# URL of the FastAPI SSE endpoint
SSE_URL = "http://localhost:8000/api/sse/stations"

###########################################################################################
# class name - SSEWorker
# parameters - QThread
# runs in a background thread and listens to the SSE stream from the FastAPI backend.
# emits new_data whenever a non-keep-alive event arrives.
###########################################################################################
class SSEWorker(QThread):
        new_data = Signal(list)   # emits parsed row data to the main thread
        error    = Signal(str)    # emits an error message string

        def __init__(self, url):
                super().__init__()
                self.url     = url
                self._active = True

        ###########################################################################################
        # function name - run(self)
        # opens the SSE stream and reads lines until stop() is called or an error occurs.
        # "data: ..." lines are parsed as JSON and emitted via new_data.
        ###########################################################################################
        def run(self):
                while self._active:
                        try:
                                with urllib.request.urlopen(self.url, timeout=10) as response:
                                        buffer = b""
                                        while self._active:
                                                chunk = response.read(1)
                                                if not chunk:
                                                        break
                                                buffer += chunk

                                                # SSE lines end with \n; events end with \n\n
                                                if buffer.endswith(b"\n"):
                                                        line = buffer.decode("utf-8").rstrip("\n")
                                                        buffer = b""

                                                        if line.startswith("data:"):
                                                                raw = line[len("data:"):].strip()
                                                                try:
                                                                        songs = json.loads(raw)
                                                                        rows  = self._parse_songs(songs)
                                                                        self.new_data.emit(rows)
                                                                except (json.JSONDecodeError, Exception):
                                                                        pass
                                                        # keep-alive comment lines (": keep-alive") are ignored

                        except Exception as e:
                                if self._active:
                                        self.error.emit(str(e))
                                        # wait 3 s before retrying so we don't spam the server
                                        self.msleep(3000)

        ###########################################################################################
        # function name - stop(self)
        # signals the worker to exit its loop on the next iteration
        ###########################################################################################
        def stop(self):
                self._active = False

        ###########################################################################################
        # function name - _parse_songs(self, json_data)
        # parameters - json_data, list of song dicts received from the server
        # mirrors the logic in the old load_song_data so the table format stays identical
        ###########################################################################################
        def _parse_songs(self, json_data):
                def clean(value):
                        if value is None:
                                return "N/A"
                        value = str(value).strip()
                        if value == "" or value.lower() == "none":
                                return "N/A"
                        return value

                loaded_data = []
                for song in json_data:
                        title   = clean(song.get("title"))
                        artist  = clean(song.get("artist"))
                        genre   = clean(song.get("genre"))
                        station = clean(song.get("station"))

                        # convert raw SNR ratio to signal strength label
                        strength_raw = song.get("strength")
                        if strength_raw is None:
                                strength = "N/A"
                        else:
                                try:
                                        snr = float(strength_raw)
                                        if snr < 9.5:
                                                strength = "Weak"
                                        elif snr < 13.0:
                                                strength = "Medium"
                                        else:
                                                strength = "Strong"
                                except (ValueError, TypeError):
                                        strength = "N/A"

                        year_raw = song.get("year")
                        if year_raw is None:
                                year_value = "N/A"
                        else:
                                year_value = str(year_raw).strip()
                                if year_value == "0" or year_value.lower() == "none" or year_value == "":
                                        year_value = "N/A"

                        loaded_data.append([title, artist, genre, year_value, station, strength])

                return loaded_data


###########################################################################################
# class name - FrontEnd
# parameters - QMainWindow
# qt creator auto generated + additions by Ben Miller
###########################################################################################
class FrontEnd(QMainWindow):
        ###########################################################################################
        # function name - __init__(self)
        # parameters - self, the application itself
        # initializes the application itself, loads .ui file and sets properties
        ###########################################################################################
        def __init__(self):
                super().__init__()

                # define the loader and what file to load in (the .ui file)
                loader = QUiLoader()
                file   = QFile("form.ui")
                file.open(QFile.ReadOnly)

                # load .ui file, update the application with the read in design, close the file
                self.ui = loader.load(file)
                file.close()

                # resize the application to match the size of the pi5 screen we will have
                self.setCentralWidget(self.ui)
                self.setFixedSize(self.ui.size())

                # create timer to use for accurate device clock widget
                self.timer = QTimer(self)
                self.timer.timeout.connect(self.update_time)
                self.timer.start(1000)

                # access table for displaying data, make it read only, and resize to fit screen
                table = self.ui.dashboard_table
                table.setEditTriggers(QAbstractItemView.NoEditTriggers)
                table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
                table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

                # variables used for click and drag scrolling on the table
                self.dragging_table  = False
                self.last_drag_pos   = None

                # install event filter so the table can be scrolled by dragging anywhere on it
                table.viewport().installEventFilter(self)
                table.viewport().setMouseTracking(True)

                # create model used for dashboard
                self.model = QStandardItemModel()

                # set headers of dashboard
                self.model.setHorizontalHeaderLabels([
                    "Title", "Artist", "Genre", "Year", "Radio Station", "Signal Strength"
                ])

                # start with an empty dataset; SSE will fill it in
                self.all_data = []
                self.load_table_data(self.all_data)

                # wrap model in a proxy so the table can be sorted by signal strength
                self.proxy_model = QSortFilterProxyModel()
                self.proxy_model.setSourceModel(self.model)
                self.proxy_model.setSortRole(Qt.UserRole)

                # attach proxy model to table for dashboard
                table.setModel(self.proxy_model)

                # enable sorting and default to signal strength descending (strong on top)
                table.setSortingEnabled(True)
                table.sortByColumn(5, Qt.DescendingOrder)

                # populate dropdown widgets (will be empty until first SSE event arrives)
                self.populate_combo_box(self.ui.genre_cmb, 2)
                self.populate_combo_box(self.ui.year_cmb_1, 3)
                self.populate_combo_box(self.ui.year_cmb_2, 3)

                # connect dropdown widgets to filter function
                self.ui.genre_cmb.currentTextChanged.connect(self.apply_filters)
                self.ui.year_cmb_1.currentTextChanged.connect(self.apply_filters)
                self.ui.year_cmb_2.currentTextChanged.connect(self.apply_filters)

                # connect reset button to reset filter function
                self.ui.resetfilter_btn.clicked.connect(self.reset_filters)

                # connect refresh signals button to restart the SSE worker
                self.ui.refreshsignals_btn.clicked.connect(self.restart_sse)

                # set reset button to be hidden initially
                self.ui.resetfilter_btn.setVisible(False)

                # start the SSE background listener
                self.sse_worker = None
                self.start_sse()

        ###########################################################################################
        # function name - start_sse(self)
        # parameters - self, the application itself
        # creates and starts the SSEWorker thread that streams data from the backend
        ###########################################################################################
        def start_sse(self):
                self.sse_worker = SSEWorker(SSE_URL)
                self.sse_worker.new_data.connect(self.on_sse_data)
                self.sse_worker.error.connect(self.on_sse_error)
                self.sse_worker.start()

        ###########################################################################################
        # function name - restart_sse(self)
        # parameters - self, the application itself
        # stops any running SSE worker and starts a fresh one (wired to the refresh button)
        ###########################################################################################
        def restart_sse(self):
                if self.sse_worker and self.sse_worker.isRunning():
                        self.sse_worker.stop()
                        self.sse_worker.wait()
                self.start_sse()

        ###########################################################################################
        # function name - on_sse_data(self, rows)
        # parameters - self, the application itself
        #            - rows, parsed list of row data emitted by SSEWorker
        # called on the main thread whenever the backend pushes new station data
        ###########################################################################################
        def on_sse_data(self, rows):
                # only update the table when no filters are active; otherwise queue the data
                self.all_data = rows

                if self.filters_are_active():
                        # keep the latest data ready but let the user's filters remain visible
                        return

                saved_filters = self.get_current_filters()
                self.reload_filter_options(saved_filters)
                self.load_table_data(self.all_data)

        ###########################################################################################
        # function name - on_sse_error(self, message)
        # parameters - self, the application itself
        #            - message, error string from SSEWorker
        # called when the SSE connection fails; the worker retries automatically
        ###########################################################################################
        def on_sse_error(self, message):
                print(f"SSE error: {message}")

        ###########################################################################################
        # function name - eventFilter(self, source, event)
        # parameters - self, the application itself
        #            - source, widget being watched for events
        #            - event, the event being handled
        # allows the table to scroll by clicking and dragging anywhere on its surface
        ###########################################################################################
        def eventFilter(self, source, event):
                table = self.ui.dashboard_table

                if source == table.viewport():
                        if event.type() == QEvent.MouseButtonPress:
                                if event.button() == Qt.LeftButton:
                                        self.dragging_table  = True
                                        self.last_drag_pos   = event.position().toPoint()
                                        table.viewport().setCursor(Qt.ClosedHandCursor)
                                        return True

                        elif event.type() == QEvent.MouseMove:
                                if self.dragging_table and self.last_drag_pos is not None:
                                        current_pos = event.position().toPoint()
                                        delta       = current_pos - self.last_drag_pos

                                        vbar = table.verticalScrollBar()
                                        hbar = table.horizontalScrollBar()

                                        vbar.setValue(vbar.value() - delta.y())
                                        hbar.setValue(hbar.value() - delta.x())

                                        self.last_drag_pos = current_pos
                                        return True

                        elif event.type() == QEvent.MouseButtonRelease:
                                if event.button() == Qt.LeftButton:
                                        self.dragging_table = False
                                        self.last_drag_pos  = None
                                        table.viewport().setCursor(Qt.ArrowCursor)
                                        return True

                return super().eventFilter(source, event)

        ###########################################################################################
        # function name - filters_are_active(self)
        # parameters - self, the application itself
        # returns true if any filter dropdown currently has a selection
        ###########################################################################################
        def filters_are_active(self):
                selected_genre      = self.ui.genre_cmb.currentText().strip()
                selected_start_year = self.ui.year_cmb_1.currentText().strip()
                selected_end_year   = self.ui.year_cmb_2.currentText().strip()

                return selected_genre != "" or selected_start_year != "" or selected_end_year != ""

        ###########################################################################################
        # function name - get_current_filters(self)
        # parameters - self, the application itself
        # returns the currently selected filter values so they can be restored after refresh
        ###########################################################################################
        def get_current_filters(self):
                return {
                        "genre":      self.ui.genre_cmb.currentText().strip(),
                        "start_year": self.ui.year_cmb_1.currentText().strip(),
                        "end_year":   self.ui.year_cmb_2.currentText().strip()
                }

        ###########################################################################################
        # function name - reload_filter_options(self, saved_filters=None)
        # parameters - self, the application itself
        #            - saved_filters, optional dictionary of existing filter selections
        # reloads the dropdown choices based on the newest song data while optionally restoring
        # previously selected filter values
        ###########################################################################################
        def reload_filter_options(self, saved_filters=None):
                self.ui.genre_cmb.blockSignals(True)
                self.ui.year_cmb_1.blockSignals(True)
                self.ui.year_cmb_2.blockSignals(True)

                self.populate_combo_box(self.ui.genre_cmb, 2)
                self.populate_combo_box(self.ui.year_cmb_1, 3)
                self.populate_combo_box(self.ui.year_cmb_2, 3)

                if saved_filters is not None:
                        genre_text      = saved_filters.get("genre", "")
                        start_year_text = saved_filters.get("start_year", "")
                        end_year_text   = saved_filters.get("end_year", "")

                        genre_index      = self.ui.genre_cmb.findText(genre_text)
                        start_year_index = self.ui.year_cmb_1.findText(start_year_text)
                        end_year_index   = self.ui.year_cmb_2.findText(end_year_text)

                        self.ui.genre_cmb.setCurrentIndex(genre_index if genre_index >= 0 else 0)
                        self.ui.year_cmb_1.setCurrentIndex(start_year_index if start_year_index >= 0 else 0)
                        self.ui.year_cmb_2.setCurrentIndex(end_year_index if end_year_index >= 0 else 0)
                else:
                        self.ui.genre_cmb.setCurrentIndex(0)
                        self.ui.year_cmb_1.setCurrentIndex(0)
                        self.ui.year_cmb_2.setCurrentIndex(0)

                self.ui.genre_cmb.blockSignals(False)
                self.ui.year_cmb_1.blockSignals(False)
                self.ui.year_cmb_2.blockSignals(False)

        ###########################################################################################
        # function name - load_table_data(self, data)
        # parameters - self, the application itself
        #            - data, the data being read in with information on songs scanned
        # loads the data from the radio scan into the table for display
        ###########################################################################################
        def load_table_data(self, data):
                self.model.setRowCount(0)

                # numeric sort keys for signal strength labels (higher = stronger)
                strength_order = {"Strong": 3, "Medium": 2, "Weak": 1, "N/A": 0}

                for row_data in data:
                        row_items = []
                        for col_index, value in enumerate(row_data):
                                item = QStandardItem(str(value))

                                # store numeric sort key on the Signal Strength column
                                if col_index == 5:
                                        item.setData(strength_order.get(str(value), 0), Qt.UserRole)

                                row_items.append(item)
                        self.model.appendRow(row_items)

        ###########################################################################################
        # function name - populate_combo_box(self, combo_box, column_index)
        # parameters - self, the application itself
        #            - combo_box, the combobox used for filter selection
        #            - column_index, a variable used to keep track of location within the data
        # sets the combobox selections to be accurate to the table's visible data
        ###########################################################################################
        def populate_combo_box(self, combo_box, column_index):
                unique_values = set()

                for row_data in self.all_data:
                        value = str(row_data[column_index]).strip()

                        # skip empty, whitespace only, invalid year values, and N/A values
                        if value == "" or value == "0" or value == "N/A":
                                continue

                        unique_values.add(value)

                combo_box.clear()
                combo_box.addItem("")

                if column_index == 3:
                        combo_box.addItems(sorted(unique_values, key=int))
                else:
                        combo_box.addItems(sorted(unique_values))

                combo_box.setCurrentIndex(0)

        ###########################################################################################
        # function name - apply_filters(self)
        # parameters - self, the application itself
        # updates the datatable to display only the data that fits the selections of the filters
        ###########################################################################################
        def apply_filters(self):
                selected_genre      = self.ui.genre_cmb.currentText().strip()
                selected_start_year = self.ui.year_cmb_1.currentText().strip()
                selected_end_year   = self.ui.year_cmb_2.currentText().strip()

                # check if any filters are in use; if so show reset button, otherwise hide it
                if selected_genre != "" or selected_start_year != "" or selected_end_year != "":
                        self.ui.resetfilter_btn.setVisible(True)
                else:
                        self.ui.resetfilter_btn.setVisible(False)
                        self.load_table_data(self.all_data)
                        self.reload_filter_options()
                        return

                filtered_data = []

                for row in self.all_data:
                        title    = row[0]
                        artist   = row[1]
                        genre    = row[2]
                        year     = row[3]
                        station  = row[4]
                        strength = row[5]

                        # filter by genre only if a genre was selected
                        if selected_genre != "" and genre.strip() != selected_genre:
                                continue

                        # only apply year filtering when a year filter is selected
                        if selected_start_year != "" or selected_end_year != "":
                                if not year.strip().isdigit():
                                        continue

                                year_int = int(year.strip())

                                if selected_start_year != "" and selected_end_year != "":
                                        start_year = int(selected_start_year)
                                        end_year   = int(selected_end_year)

                                        if start_year > end_year:
                                                start_year, end_year = end_year, start_year

                                        if year_int < start_year or year_int > end_year:
                                                continue

                                elif selected_start_year != "":
                                        if year_int < int(selected_start_year):
                                                continue

                                elif selected_end_year != "":
                                        if year_int > int(selected_end_year):
                                                continue

                        filtered_data.append([title, artist, genre, year, station, strength])

                self.load_table_data(filtered_data)

        ###########################################################################################
        # function name - reset_filters(self)
        # parameters - self, the application itself
        # resets all filter combo boxes back to empty, reloads song data, and reloads full table
        ###########################################################################################
        def reset_filters(self):
                self.reload_filter_options()
                self.ui.resetfilter_btn.setVisible(False)
                self.load_table_data(self.all_data)

        ###########################################################################################
        # function name - update_time
        # parameters - self, the application itself
        # sets the text label at the top of the screen to the current time based on the device
        ###########################################################################################
        def update_time(self):
                self.ui.time_lbl.setText(QTime.currentTime().toString("hh:mm"))

        ###########################################################################################
        # function name - closeEvent(self, event)
        # cleanly stops the SSE worker thread when the window is closed
        ###########################################################################################
        def closeEvent(self, event):
                if self.sse_worker and self.sse_worker.isRunning():
                        self.sse_worker.stop()
                        self.sse_worker.wait()
                super().closeEvent(event)


###########################################################################################
# you just do this in python, runs the program and defines the window as the frontend,
# then shows the window
###########################################################################################
if __name__ == "__main__":
        app = QApplication(sys.argv)

        window = FrontEnd()
        window.show()

        sys.exit(app.exec())
