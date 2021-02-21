import kivy
from kivy.app import App
from kivy.config import Config

from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button

from kivy.core.window import Window
import crepe
import music21
from music21.converter.subConverters import ConverterMusicXML
import numpy as np
import os
from scipy.io import wavfile
import pygame

Config.set('graphics', 'resizable', 1)
Window.size = (400, 750)
pathtofile = ''

class NoFileFed(FloatLayout):
    pass

class Error(FloatLayout):
    pass

class BrowseFile(FloatLayout):
    def F(self, path):
        global pathtofile
        try:
            fpath = str(path)
            filepath = fpath[2:len(fpath)-2]
            last3 = filepath[len(filepath)-3:]

            if (last3 != 'wav'):
                popupW = Popup(title = 'Error', content = Error(), size_hint = (0.5, 0.3))
                popupW.open()

            else:
                print('This is a wav file')
                pathtofile = filepath
                print(pathtofile)
        except:
            pass
        
class MainMenu(BoxLayout):
    popupWindow = None
    
    def show_popup(self):
        box = BoxLayout(orientation = 'vertical')
        self.popupWindow = Popup(title="Open File", content = BrowseFile(), size_hint = (0.9, 0.8), pos_hint = {'x': 0.05, 'y': 0.1}, auto_dismiss = True)
        self.popupWindow.open()

        return self.popupWindow

    def new(self, instance):
        instance.back_color[3] -= 0.3
        
    def old(self, instance):
        instance.back_color[3] += 0.3
        
    def playSound(arg):
        pygame.init()
        try:
            pygame.mixer.music.load("Test.mid")
            pygame.mixer.music.play()
        except:
            popupW = Popup(title = 'Error', content = NoFileFed(), size_hint = (0.8, 0.3))
            popupW.open()

    def convert(arg):
        try:
            print(pathtofile)
            GenerateFile(pathtofile)
        except:
            popupW = Popup(title = 'Error', content = NoFileFed(), size_hint = (0.8, 0.3))
            popupW.open()
    pass

class VtMApp(App):
    version = kivy.__version__
    title = "Voice to Midi Converter - Kivy " + version
    def build (self):
        Window.bind(on_dropfile=self._on_file_drop)
        return MainMenu()

    def _on_file_drop(self, window, path):
        global pathtofile
        fpath = str(path)

        filepath = fpath[2:len(fpath)-1]
        last3 = filepath[len(filepath)-3:]

        if (last3 != 'wav'):
                popupW = Popup(title='Error', content = Error(), size_hint = (0.5, 0.3))
                popupW.open()
        else:
                print("this is a wav file")
                pathtofile = filepath
                print(pathtofile)


def GenerateFile(filename):

    #CONSTANTS
    #./amazing_grace_female.wav
    confidence_threshold = 0.6 #CREPE must be at least this confident about a note's pitch for it to count
    tuning_freq = 440 #Root of tuning system (the default value here reflects A440)
    min_duration = 4 #The least number of frames in a row that must hold a pitch to register as a note
    #DISCARD_THRESH MUST BE AT LEAST 3 OR THE PROGRAM WILL CRASH hard-code this into the interface and it will be fine
    discard_thresh = 3 #"Notes" and indeterminate-frequency patches this many frames or shorter are discarded or replaced

  
    address = filename#input("Enter path of audio file\n")
   
    sr, audio = wavfile.read(address)
        
    time, frequency, confidence, activation = crepe.predict(audio, sr, viterbi=True)

    #Eliminate low-confidence or indeterminate-frequency estimates
    for i in range(frequency.size):
        if frequency[i] <= 0 or confidence[i] < confidence_threshold:
            frequency[i] = 0

    #Convert frequencies to MIDI numbers
    midi = []
    for i in range(frequency.size):
        if (frequency[i]) > 0:
            note = round(np.log2(frequency[i]/tuning_freq)*12+69)
            midi = np.append(midi, note)
        else:
            midi = np.append(midi, 0)


    #The complicated part:
    #ironing out short pitch wobbles & vacant/uncertain-pitch deviations
    #by replacing their MIDI numbers with those of their neighbours
    # print("midi before")
    # print(midi)

    #Prep: add one extra zero to the midi array so that Pass 1 doesn't have trouble at the end of the array
    midi = np.append(midi, 0)

    #Pass 1: replace too-short tones with zeroes
    count = 1
    for frame in range(midi.size-1):
        if midi[frame] == midi[frame+1]:
            count += 1 #count the number of identical pitches in a row
        else:
            if count <= discard_thresh: #if tone is too short to be counted
                for i in range(0, count):
                    midi[frame-i] = 0 #kablammo
            count = 1 #reset counter; you now have precisely one of the same numbers in a row

    # print("midi after too-short-tones' replacement with zeroes but before filling in gaps with good tones")
    # print(midi)

    #Pass 2: fill in too-short patches of zeroes with the tone immediately following them
    count = 0
    for frame in range(midi.size):
        if midi[frame] == 0:
            count += 1 #count the number of zeroes in a row
        else:
            if count <= discard_thresh: #if streak of zeros is too short to be counted
                if frame + discard_thresh + 1 <= midi.size: #if there are enough frames left in the midi array
                    standard = midi[frame+1] #do the following frames match this one?
                    good_trailing = True #Represents whether there is a long-enough tone after the streak of zeroes to fill it in with
                    for i in range(frame+2, frame+discard_thresh+1):
                        if midi[i] != standard:
                            good_trailing = False
                            break
                    if (good_trailing):
                        for i in range(count):
                            midi[frame-i-1] = standard #kablammo
            count = 0

    #Finally, let's generate a list of MIDI notes
    #expressed as trios of numbers: MIDI number, start time (ms), end time (ms), length(ms)
    final = np.array([[0,0,0,0]])
    hold_freq = midi[0]
    start_frame = 0
    for frame in range(1, midi.size):
        if midi[frame] != hold_freq:
            if hold_freq != 0:
                data = np.array([[hold_freq, start_frame*10, frame*10, frame*10-start_frame*10]])
                final = np.concatenate([final, data],axis=0)
            hold_freq = midi[frame]
            start_frame = frame

    # Need to use MuseScore to show music score
    # Set up path to the installed 

    env = music21.environment.Environment()
    # check the path
    #print('Environment settings:')
    #print('musicXML:  ', env['musicxmlPath'])
    #print('musescore: ', env['musescoreDirectPNGPath'])
    env['musescoreDirectPNGPath'] = 'C:\Program Files (x86)\MuseScore 3\\bin\\MuseScore3.exe'
    env['musicxmlPath'] = 'C:\Program Files (x86)\MuseScore 3\\bin\\MuseScore3.exe'
    #print('musescore: ', env['musescoreDirectPNGPath'])

    #One possible way to clamp each output duration to music note duration
    # note_durations = np.array([1/64, 1/32, 1/16, 1/8, 1/4, 1/2, 1])
    # def find_nearest(array, value):
    #     array = np.asarray(array)
    #     idx = (np.abs(array - value)).argmin()
    #     return array[idx]


    midi_stream = music21.stream.Stream()
    #Initial sound is not played, so append empty sound.
    n = music21.note.Note(0)
    midi_stream.append(n)
    sum_time = 0

    for x in final:
        min_length = 16
        dur = x[3] 
        dur /= 1000.0 #convert to sec
        dur *= min_length #clamp duration into 128th duration type
        dur = round(dur) 
        n = music21.note.Note(x[0])
        n.duration.quarterLength -= 1
        n.duration.quarterLength += dur / min_length
        if n.quarterLength > 0.0:
            midi_stream.append(n)
            sum_time += dur / min_length

    fp=midi_stream.write('xml', fp='./Test.xml')
    fp=midi_stream.write('midi', fp='./Test.mid')
    conv_musicxml = ConverterMusicXML()
    out_filepath = conv_musicxml.write(midi_stream, 'musicxml', fp='./Test.xml', subformats=['png'])

    print("done!")



if __name__ == '__main__':
   VtMApp().run()
