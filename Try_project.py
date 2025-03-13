import pygame
import time
import numpy as np
import soundfile as sf
import tkinter as tk
from tkinter import filedialog
from blackboard import parse_midi, generate_audio  


pygame.init()
pygame.mixer.init()

WIDTH, HEIGHT = 1500, 1000
GRID_ROWS = 16
INITIAL_GRID_COLS = 16
CELL_SIZE = 40
FIXED_COL_X_RATIO = 0.1

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
BLUE = (0, 100, 255)
LIGHT_BLUE = (173, 216, 230)
RED = (255, 0, 0)

screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("PixelTone - 8-bit Music Sequencer")
font = pygame.font.Font(None, 36)


is_playing = False
bps = 2  
playbar_x = 0
playbar_interval = 1 / bps
last_update_time = time.time()


SLIDER_MIN_COLUMNS = 4
SLIDER_MAX_COLUMNS = 32
slider_columns = INITIAL_GRID_COLS

SLIDER_MIN_BPS = 1
SLIDER_MAX_BPS = 10
slider_bps = bps


grid = [[0 for _ in range(INITIAL_GRID_COLS)] for _ in range(GRID_ROWS)]


FREQUENCIES = [523, 494, 466, 440, 392, 349, 330, 294, 262, 
               247, 220, 196, 175, 165, 147, 131]


def generate_square_wave(freq, duration=0.2, sample_rate=44100):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = 0.5 * (1 + np.sign(np.sin(2 * np.pi * freq * t)))
    wave = (wave * 32767).astype(np.int16)
    return pygame.mixer.Sound(buffer=wave.tobytes())


SOUNDS = [generate_square_wave(freq) for freq in FREQUENCIES]

def update_grid_size(new_cols):
    global grid
    for r in range(GRID_ROWS):
        grid[r] = grid[r][:new_cols] + [0] * max(0, new_cols - len(grid[r]))

def get_fixed_col_x():
    return int(WIDTH * FIXED_COL_X_RATIO)


def draw_grid(play_col=None):
    fixed_col_x = get_fixed_col_x()
    top_offset = (HEIGHT - GRID_ROWS * CELL_SIZE - 160) // 2

    if play_col is not None:
        for row in range(GRID_ROWS):
            x = fixed_col_x + play_col * CELL_SIZE
            y = top_offset + row * CELL_SIZE
            pygame.draw.rect(screen, (200, 230, 255, 120), (x, y, CELL_SIZE, CELL_SIZE))  

    for row in range(GRID_ROWS):
        for col in range(slider_columns):
            x = fixed_col_x + col * CELL_SIZE
            y = top_offset + row * CELL_SIZE

            if grid[row][col]:
                pygame.draw.rect(screen, BLUE, (x, y, CELL_SIZE, CELL_SIZE))
                
            pygame.draw.rect(screen, BLACK, (x, y, CELL_SIZE, CELL_SIZE), 2)

play_button = pygame.Rect(50, HEIGHT - 120, 100, 50)
stop_button = pygame.Rect(200, HEIGHT - 120, 100, 50)
clear_button = pygame.Rect(500, HEIGHT - 120, 100, 50)

slider_columns_box = pygame.Rect(650, HEIGHT - 120, 300, 10) 
slider_bps_box = pygame.Rect(650, HEIGHT - 80, 300, 10)  

upload_button = pygame.Rect(1150, HEIGHT - 120, 130, 50)  
download_button = pygame.Rect(1300, HEIGHT - 120, 150, 50)  

uploaded_midi = None  
generated_audio = None  


def draw_controls():
    pygame.draw.rect(screen, BLUE, play_button)
    pygame.draw.rect(screen, BLUE, stop_button)
    pygame.draw.rect(screen, RED, clear_button)
    
    pygame.draw.rect(screen, (0, 200, 0), upload_button)  
    pygame.draw.rect(screen, (200, 200, 0), download_button) 
    
    screen.blit(font.render("Play", True, WHITE), (play_button.x + 25, play_button.y + 10))
    screen.blit(font.render("Stop", True, WHITE), (stop_button.x + 25, stop_button.y + 10))
    screen.blit(font.render("Clear", True, WHITE), (clear_button.x + 15, clear_button.y + 10))
    
    screen.blit(font.render("Upload", True, WHITE), (upload_button.x + 15, upload_button.y + 10))
    screen.blit(font.render("Download", True, BLACK), (download_button.x + 15, download_button.y + 10))
    

    button_center_x = (upload_button.x + download_button.x + download_button.width) // 2
    status_y = upload_button.y 
    status_text = font.render(status_message, True, BLACK)
    screen.blit(status_text, (button_center_x - status_text.get_width() // 2, status_y - 40))

    # Column Slider
    pygame.draw.rect(screen, BLACK, slider_columns_box)
    knob_x = 650 + (slider_columns - SLIDER_MIN_COLUMNS) * (300 / (SLIDER_MAX_COLUMNS - SLIDER_MIN_COLUMNS))
    pygame.draw.circle(screen, BLUE, (int(knob_x), slider_columns_box.y + 5), 10)
    screen.blit(font.render(f"Columns: {slider_columns}", True, BLACK), (960, slider_columns_box.y - 5))

    # BPS Slider
    pygame.draw.rect(screen, BLACK, slider_bps_box)
    knob_x = 650 + (slider_bps - SLIDER_MIN_BPS) * (300 / (SLIDER_MAX_BPS - SLIDER_MIN_BPS))
    pygame.draw.circle(screen, BLUE, (int(knob_x), slider_bps_box.y + 5), 10)
    screen.blit(font.render(f"BPS: {slider_bps}", True, BLACK), (960, slider_bps_box.y - 5))


status_message = "Waiting for user action..."
def update_status(new_status):

    global status_message
    status_message = new_status  
    button_center_x = (upload_button.x + download_button.x + download_button.width) // 2
    status_y = upload_button.y - 40 

    pygame.draw.rect(screen, GRAY, (button_center_x - 150, status_y - 5, 300, 30))

    status_text = font.render(status_message, True, BLACK)
    screen.blit(status_text, (button_center_x - status_text.get_width() // 2, status_y))  # **让文本对齐按钮中心**

    pygame.display.update((button_center_x - 150, status_y - 5, 300, 30))



    
def upload_midi():
    global uploaded_midi, generated_audio
    root = tk.Tk()
    root.withdraw()
    
    file_path = filedialog.askopenfilename(filetypes=[("MIDI files", "*.mid")])
    if file_path:
        update_status("Uploading MIDI file...")
        uploaded_midi = file_path

        update_status("Parsing MIDI file...")
        notes = parse_midi(uploaded_midi)

        update_status("Generating audio...")
        generated_audio = generate_audio(notes)

        update_status("Generation complete!")


def download_audio():
    global status_message
    if generated_audio is not None:
        status_message = "Saving the file..."
        update_status("Saving the file...")

        save_path = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV files", "*.wav")])
        if save_path:
            sf.write(save_path, generated_audio, samplerate=44100)

            status_message = "Audio saved!"
            update_status("Audio saved!")


def play_column(col):
    for row in range(GRID_ROWS):
        if col < len(grid[row]) and grid[row][col] == 1:
            SOUNDS[row].play()


def handle_mouse_click(pos):
    global is_playing, playbar_x, slider_columns, slider_bps, grid, bps, playbar_interval
    x, y = pos

    if play_button.collidepoint(x, y):
        is_playing = True
        playbar_x = get_fixed_col_x()
    elif stop_button.collidepoint(x, y):
        is_playing = False
    elif clear_button.collidepoint(x, y):
        grid = [[0 for _ in range(slider_columns)] for _ in range(GRID_ROWS)]
    elif slider_columns_box.collidepoint(x, y):  
        slider_columns = SLIDER_MIN_COLUMNS + int((x - 650) / 300 * (SLIDER_MAX_COLUMNS - SLIDER_MIN_COLUMNS))
        slider_columns = max(SLIDER_MIN_COLUMNS, min(SLIDER_MAX_COLUMNS, slider_columns))
        update_grid_size(slider_columns)
    elif slider_bps_box.collidepoint(x, y):  
        slider_bps = SLIDER_MIN_BPS + int((x - 650) / 300 * (SLIDER_MAX_BPS - SLIDER_MIN_BPS))
        slider_bps = max(SLIDER_MIN_BPS, min(SLIDER_MAX_BPS, slider_bps))
        bps = slider_bps
        playbar_interval = 1 / bps
        
    elif upload_button.collidepoint(x, y):
        upload_midi()  

    elif download_button.collidepoint(x, y):
        download_audio()  
        
    else:
        fixed_col_x = get_fixed_col_x()
        top_offset = (HEIGHT - GRID_ROWS * CELL_SIZE - 160) // 2
        col = (x - fixed_col_x) // CELL_SIZE
        row = (y - top_offset) // CELL_SIZE
        if 0 <= row < GRID_ROWS and 0 <= col < slider_columns:
            grid[row][col] = 1 - grid[row][col]  


def main():
    global playbar_x, last_update_time, is_playing
    running = True
    while running:
        screen.fill(GRAY)
        col = (playbar_x - get_fixed_col_x()) // CELL_SIZE if is_playing else None
        draw_grid(col)
        draw_controls()

        if is_playing:
            current_time = time.time()
            if current_time - last_update_time >= playbar_interval:
                last_update_time = current_time
                if 0 <= col < slider_columns:
                    play_column(col)
                playbar_x += CELL_SIZE
                if playbar_x > get_fixed_col_x() + (slider_columns - 1) * CELL_SIZE:
                    playbar_x = get_fixed_col_x()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                handle_mouse_click(event.pos)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()




