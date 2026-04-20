###########################################################################################
# Daniel, David, Ben (DDB)
# CSC 363
# frontend.py
# Last modified: April 16, 2026
# purpose: frontend to be used in 363 project. created using qt creator and pyside6.
###########################################################################################

# imports
import sys
import json
from PySide6.QtWidgets import QApplication, QMainWindow, QHeaderView, QAbstractItemView
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, QTimer, QTime, Qt, QEvent
from PySide6.QtGui import QStandardItemModel, QStandardItem

###########################################################################################
# class name - frontend
# parameters - QMainWindow, an item that is passed to define the app as the main window
# qt creator auto generated + additions by Ben Miller
###########################################################################################
class FrontEnd(QMainWindow):
        ###########################################################################################
        # function name - __init__(self)
        # parameters - self, the application itself
        # initializes the application itself, loads ,ui file and sets properties
        ###########################################################################################
        def __init__(self):
                super().__init__()

                # define the loader and what file to load in (the .ui file)
                loader = QUiLoader()
                file = QFile("form.ui")
                file.open(QFile.ReadOnly)

                # load .ui file, update the application with the read in design, close the file
                self.ui = loader.load(file)
                file.close()

                # rezise the application to match the size of the pi5 screen we will have
                self.setCentralWidget(self.ui)
                self.setFixedSize(self.ui.size())

                # create timer to use for accurate device clock widget
                self.timer = QTimer(self)
                self.timer.timeout.connect(self.update_time)
                self.timer.start(1000)

                # create timer to auto refresh song data every 3 minutes
                self.refresh_timer = QTimer(self)
                self.refresh_timer.timeout.connect(self.auto_refresh_song_data)
                self.refresh_timer.start(185000)

                # access table for displaying data, make it read only, and rezise to fit screen
                table = self.ui.dashboard_table
                table.setEditTriggers(QAbstractItemView.NoEditTriggers)
                table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
                table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

                # variables used for click and drag scrolling on the table
                self.dragging_table = False
                self.last_drag_pos = None

                # install event filter so the table can be scrolled by dragging anywhere on it
                table.viewport().installEventFilter(self)
                table.viewport().setMouseTracking(True)

                # create model used for dashboard
                self.model = QStandardItemModel()

                # set headers of dashboard
                self.model.setHorizontalHeaderLabels([
                    "Title", "Artist", "Genre", "Year", "Radio Station"
                ])

                # load song data from json file
                self.all_data = self.load_song_data("songs.json")

                # load all data into model first
                self.load_table_data(self.all_data)

                # attach model to table for dashboard
                table.setModel(self.model)

                # populate dropdown widgets with unique values
                self.populate_combo_box(self.ui.genre_cmb, 2)
                self.populate_combo_box(self.ui.year_cmb_1, 3)
                self.populate_combo_box(self.ui.year_cmb_2, 3)

                # connect dropdown widgets to filter function
                self.ui.genre_cmb.currentTextChanged.connect(self.apply_filters)
                self.ui.year_cmb_1.currentTextChanged.connect(self.apply_filters)
                self.ui.year_cmb_2.currentTextChanged.connect(self.apply_filters)

                # connect reset button to reset filter function
                self.ui.resetfilter_btn.clicked.connect(self.reset_filters)

                # connect refresh signals button to reload song data function
                self.ui.refreshsignals_btn.clicked.connect(self.reload_song_data)

                # set reset button to be hidden initially
                self.ui.resetfilter_btn.setVisible(False)

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
                                        self.dragging_table = True
                                        self.last_drag_pos = event.position().toPoint()
                                        table.viewport().setCursor(Qt.ClosedHandCursor)
                                        return True

                        elif event.type() == QEvent.MouseMove:
                                if self.dragging_table and self.last_drag_pos is not None:
                                        current_pos = event.position().toPoint()
                                        delta = current_pos - self.last_drag_pos

                                        vbar = table.verticalScrollBar()
                                        hbar = table.horizontalScrollBar()

                                        vbar.setValue(vbar.value() - delta.y())
                                        hbar.setValue(hbar.value() - delta.x())

                                        self.last_drag_pos = current_pos
                                        return True

                        elif event.type() == QEvent.MouseButtonRelease:
                                if event.button() == Qt.LeftButton:
                                        self.dragging_table = False
                                        self.last_drag_pos = None
                                        table.viewport().setCursor(Qt.ArrowCursor)
                                        return True

                return super().eventFilter(source, event)

        ###########################################################################################
        # function name - filters_are_active(self)
        # parameters - self, the application itself
        # returns true if any filter dropdown currently has a selection
        ###########################################################################################
        def filters_are_active(self):
                selected_genre = self.ui.genre_cmb.currentText().strip()
                selected_start_year = self.ui.year_cmb_1.currentText().strip()
                selected_end_year = self.ui.year_cmb_2.currentText().strip()

                return selected_genre != "" or selected_start_year != "" or selected_end_year != ""

        ###########################################################################################
        # function name - start_refresh_timer(self)
        # parameters - self, the application itself
        # starts or restarts the 3 minute auto refresh timer
        ###########################################################################################
        def start_refresh_timer(self):
                self.refresh_timer.start(185000)

        ###########################################################################################
        # function name - stop_refresh_timer(self)
        # parameters - self, the application itself
        # stops the auto refresh timer while filters are being used
        ###########################################################################################
        def stop_refresh_timer(self):
                self.refresh_timer.stop()

        ###########################################################################################
        # function name - reload_filter_options(self)
        # parameters - self, the application itself
        # reloads the dropdown choices based on the newest song data while keeping blank selected
        ###########################################################################################
        def reload_filter_options(self):
                self.ui.genre_cmb.blockSignals(True)
                self.ui.year_cmb_1.blockSignals(True)
                self.ui.year_cmb_2.blockSignals(True)

                self.populate_combo_box(self.ui.genre_cmb, 2)
                self.populate_combo_box(self.ui.year_cmb_1, 3)
                self.populate_combo_box(self.ui.year_cmb_2, 3)

                self.ui.genre_cmb.setCurrentIndex(0)
                self.ui.year_cmb_1.setCurrentIndex(0)
                self.ui.year_cmb_2.setCurrentIndex(0)

                self.ui.genre_cmb.blockSignals(False)
                self.ui.year_cmb_1.blockSignals(False)
                self.ui.year_cmb_2.blockSignals(False)

        ###########################################################################################
        # function name - auto_refresh_song_data(self)
        # parameters - self, the application itself
        # refreshes song data automatically only when no filters are active
        ###########################################################################################
        def auto_refresh_song_data(self):
                if self.filters_are_active():
                        self.stop_refresh_timer()
                        return

                self.all_data = self.load_song_data("songs.json")
                self.load_table_data(self.all_data)
                self.reload_filter_options()

                self.ui.resetfilter_btn.setVisible(False)

        ###########################################################################################
        # function name - load_song_data(self, filename)
        # parameters - self, the application itself
        #            - filename, the json file containing scanned song information
        # reads the json file and converts the song objects into row data for the table
        ###########################################################################################
        def load_song_data(self, filename):
                try:
                        with open(filename, "r", encoding="utf-8") as file:
                                json_data = json.load(file)

                        loaded_data = []

                        for song in json_data:
                                loaded_data.append([
                                        str(song.get("title", "")),
                                        str(song.get("artist", "")),
                                        str(song.get("genre", "")),
                                        str(song.get("year", "")),
                                        str(song.get("station", ""))
                                ])

                        return loaded_data

                except FileNotFoundError:
                        print(f"Error: {filename} was not found.")
                        return []

                except json.JSONDecodeError:
                        print(f"Error: {filename} is not valid json.")
                        return []

        ###########################################################################################
        # function name - reload_song_data(self)
        # parameters - self, the application itself
        # rereads the json song file, reloads the table data, resets the filters, and updates
        # the combo boxes to match the most recent song data
        ###########################################################################################
        def reload_song_data(self):
                self.all_data = self.load_song_data("songs.json")
                self.load_table_data(self.all_data)
                self.reload_filter_options()

                self.ui.resetfilter_btn.setVisible(False)

                # restart the 3 minute refresh timer after manual refresh
                self.start_refresh_timer()

        ###########################################################################################
        # function name - load_table_data(self, data)
        # parameters - self, the application itself
        #            - data, the data being read in with information on songs scanned
        # loads the data from the radio scan into the table for display
        ###########################################################################################
        def load_table_data(self, data):
                self.model.setRowCount(0)

                for row_data in data:
                        row_items = []
                        for value in row_data:
                                item = QStandardItem(str(value))
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
                        unique_values.add(str(row_data[column_index]))

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
                selected_genre = self.ui.genre_cmb.currentText().strip()
                selected_start_year = self.ui.year_cmb_1.currentText().strip()
                selected_end_year = self.ui.year_cmb_2.currentText().strip()

                # check if any filters are in use, if so show reset button, otherwise hide it
                if selected_genre != "" or selected_start_year != "" or selected_end_year != "":
                        self.ui.resetfilter_btn.setVisible(True)
                        self.stop_refresh_timer()
                else:
                        self.ui.resetfilter_btn.setVisible(False)

                        # reload newest song data when all filters are cleared
                        self.all_data = self.load_song_data("songs.json")
                        self.load_table_data(self.all_data)
                        self.reload_filter_options()

                        self.start_refresh_timer()
                        return

                filtered_data = []

                for row in self.all_data:
                        title = row[0]
                        artist = row[1]
                        genre = row[2]
                        year = row[3]
                        station = row[4]

                        # filter by genre only if a genre was selected
                        if selected_genre != "" and genre != selected_genre:
                                continue

                        # filter by year range only if a year was selected
                        try:
                                year_int = int(year)
                        except ValueError:
                                continue

                        if selected_start_year != "" and selected_end_year != "":
                                start_year = int(selected_start_year)
                                end_year = int(selected_end_year)

                                if start_year > end_year:
                                        start_year, end_year = end_year, start_year

                                if year_int < start_year or year_int > end_year:
                                        continue

                        elif selected_start_year != "":
                                start_year = int(selected_start_year)
                                if year_int < start_year:
                                        continue

                        elif selected_end_year != "":
                                end_year = int(selected_end_year)
                                if year_int > end_year:
                                        continue

                        filtered_data.append([title, artist, genre, year, station])

                self.load_table_data(filtered_data)

        ###########################################################################################
        # function name - reset_filters(self)
        # parameters - self, the application itself
        # resets all filter combo boxes back to empty, reloads song data, and reloads full table
        ###########################################################################################
        def reset_filters(self):
                # reload newest song data when filters are cleared
                self.all_data = self.load_song_data("songs.json")

                # update combo boxes to match newest data and clear selections
                self.reload_filter_options()

                # hide reset button again after filters are cleared
                self.ui.resetfilter_btn.setVisible(False)

                # reload full table with newest data
                self.load_table_data(self.all_data)

                # restart auto refresh once filters are cleared
                self.start_refresh_timer()

        ###########################################################################################
        # function name - update_time
        # parameters - self, the application itself
        # sets the text label at the top of the screen to the current time based on the device
        ###########################################################################################
        def update_time(self):
                self.ui.time_lbl.setText(QTime.currentTime().toString("hh:mm"))

###########################################################################################
# you just do this in python, runs the program and defines the window as the frontend,
# then shows the window
###########################################################################################
if __name__ == "__main__":
        app = QApplication(sys.argv)

        window = FrontEnd()
        window.show()

        sys.exit(app.exec())