import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, simpledialog
from PIL import Image, ImageTk, ImageEnhance, ImageOps, ImageDraw, ImageFont
import os
from google import genai
import threading
import time
# --- 1. 設定エリア ---
API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash-lite"
INPUT_IMG = "new_base_kiti.png"
FINAL_IMG = "wall_paper.png"

class HimitsuKichiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("滋賀 秘密基地")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.root.geometry("1280x780")
        self.root.resizable(False,False)
        self.root.configure(bg="black")

        self.client = genai.Client(api_key=API_KEY)
        
        # 吹き出し画像
        # 1個目: しっぽあり / 2個目以降: しっぽなし
        self.bubble_tail_img = Image.open("hukidasi2-1.png").convert("RGBA")
        self.bubble_plain_img = Image.open("hukidasi2-2.png").convert("RGBA")
        self.resized_bubble_cache = {}

        self.system_prompt = """

        1行目は必ず:
        [speaker=zyemio/gigao][emotion=normal/happy/angry/cry/surprise]

        2行目以降は必ず:
        【じぇみお】または【ギガお】から開始

        
        重要：じぇみおとギガおで、ユーザーが関わらない掛け合いをターン性で行う。（回数は２～６回以内）
        健康管理・人生訓・一般的なアドバイスを勝手に始めない。つまり「役になりきれ」

        じぇみお:
        渋いおじさん。渋いが感情は豊か。共感的。一人称は「私」
        語尾は「だ」「だな」「だろ」「するぞ」「違う」

        ギガお:
        論理的なおじさん。男性的で淡々と話す。解説役。たまに否定的。一人称は「私」
        語尾は「だ」「だな」「だろ」「するぞ」「違う」「問題ない」。

        会話形式で答える。
        """

        self.chat = self.client.chats.create(
            model=MODEL_NAME,
            config={
                "system_instruction": self.system_prompt
            }
        )

        self.ratio = 16 / 9
        self.bg_photo = None
        self.is_busy = False
        self.history_visible = False
        self.bubble_photos = []
        self.history_logs = []
        self.character_images = {}
        self.character_photo = {}
        self.jemio_id = None
        self.gigao_id = None
        self.current_jemio = "normal"
        self.current_gigao = "normal"
        self.last_input_empty = True
        self.speech_photo = None
        self.speech_photos = [None, None, None]
        self.speech_pages = ["", "", ""]
        self.speech_active_slot = 0
        self.speech_pending_clear = False
        self.speech_page_line_limit = 4          # 1つの吹き出しは最大4行
        self.speech_switch_after_lines = 3       # 3行目以降で句読点が来たら次へ移る
        self.speech_line_chars = 18
        self.speech_previous_text = ""
        self.speech_delete_after_id = None
        self.speech_font = ImageFont.truetype("C:/Windows/Fonts/msgothic.ttc", 20)
        self.speech_bubble = None
        self.loading_animation_running = False
        self.bubble_photo = None
        self.dot_font = ImageFont.truetype("C:/Windows/Fonts/msgothic.ttc", 24)

        # ストリーミング表示用
        self.stream_queue = []
        self.stream_display_text = ""
        self.stream_full_text = ""
        self.stream_default_speaker = None
        self.stream_api_done = False
        self.stream_typing_running = False
        self.stream_finished_once = False

        # --- 2. UI構築 ---
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bg="black")
        self.canvas.pack(fill=tk.X, expand=False)

        # ログ表示エリア（下部30%に配置）
        self.log_frame = ctk.CTkFrame(
            self.root,
            corner_radius=20,
            fg_color="#151515"
        )
        self.log_frame.place(relx=0.05, rely=0.6, relwidth=0.9, relheight=0.25)

        self.log_box = tk.Text(self.log_frame, font=("MS Gothic", 11), bg="#111111", fg="white", 
                              state=tk.DISABLED, wrap=tk.WORD, bd=0, padx=10, pady=10)
        self.scrollbar = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=self.scrollbar.set)
        
        self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # クイックボタンエリア
        self.quick_frame = tk.Frame(self.root, bg="#111111")
        self.quick_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=20, pady=(0, 5))

        self.weather_btn = ctk.CTkButton(
            self.quick_frame,
            text="今日の天気は？？？",
            command=lambda: self.quick_send("今日の滋賀の天気を教えて"),
            corner_radius=15,
            fg_color="#2b2b2b",
            hover_color="#3a3a3a",
            text_color="white",
            height=38
        )
        self.weather_btn.pack(side=tk.LEFT, padx=5)

        # 入力エリア

        self.entry_frame = tk.Frame(self.root, bg="black")
        self.entry_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=20, pady=10)

        self.history_btn = ctk.CTkButton(
            self.entry_frame,
            text="▼",
            command=self.toggle_history,
            corner_radius=15,
            fg_color="#2b2b2b",
            hover_color="#3a3a3a",
            text_color="white",
            width=80
        )
        self.history_btn.pack(side=tk.RIGHT, padx=(0, 8))

        self.send_btn = ctk.CTkButton(
            self.entry_frame,
            text="語る",
            command=self.send_message,
            corner_radius=15,
            fg_color="#2b2b2b",
            hover_color="#3a3a3a",
            text_color="white",
            width=80,
            height=45
        )
        self.send_btn.pack(side=tk.RIGHT)
        
        self.input_box = ctk.CTkTextbox(
            self.entry_frame,
            font=("MS Gothic", 14),
            corner_radius=15,
            fg_color="#222222",
            text_color="white",
            height=60
        )
        self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.input_box.bind("<Return>", self.send_message_safe)
        self.input_box._textbox.bind("<Return>", self.send_message_safe)
        self.input_box._textbox.bind("<Shift-Return>", self.insert_newline)
        self.input_box._textbox.bind("<KeyRelease>", self.reset_expressions)
        self.input_box.focus_set()

        self.load_character_images()
        self.root.bind("<Configure>", self.on_resize)
        self.update_log("【じぇみお】: お疲れさん、相棒。基地の再起動、完了だ。")
        


    def load_character_images(self):
        characters = ["zyemio", "gigao"]
        emotions = ["normal", "happy", "angry", "cry", "surprise", "thinking"]

        for char in characters:
            self.character_images[char] = {}
            for emo in emotions:
                
                filename = f"new_{char}_{emo}.png"
                if os.path.exists(filename):
                    img = Image.open(filename).convert("RGBA")
                    if char == "zyemio":
                        img = ImageOps.mirror(img)
                    self.character_images[char][emo] = img
                else:
                    print("立ち絵が見つからない:", filename)

    def make_character_photo(self, char, emotion, scale=0.42, alpha=255, brightness=1.0):
        img = self.character_images[char][emotion].copy()

        w, h = img.size
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        if alpha < 255:
            r, g, b, a = img.split()
            a = ImageEnhance.Brightness(a).enhance(alpha / 255)
            img.putalpha(a)

        img = ImageEnhance.Brightness(img).enhance(brightness)

        photo = ImageTk.PhotoImage(img)
        return photo

    def show_characters(self, jemio_emotion="normal", gigao_emotion="normal", speaker=None):
        if not self.character_images:
            return

        self.canvas.delete("character")

        jemio_brightness = 1.0
        gigao_brightness = 1.0

        if speaker == "zyemio":
            gigao_brightness = 0.55
        elif speaker == "gigao":
            jemio_brightness = 0.55

        # 立ち絵をデカくする
        self.character_photo["zyemio"] = self.make_character_photo(
            "zyemio", jemio_emotion, scale=0.46, brightness=jemio_brightness
        )
        self.character_photo["gigao"] = self.make_character_photo(
            "gigao", gigao_emotion, scale=0.46, brightness=gigao_brightness
        )

        w = self.root.winfo_width()
        h = self.canvas.winfo_height()

        # もっと画面端へ
        self.jemio_id = self.canvas.create_image(
            int(w * 0.16),
            int(h * 0.96),
            image=self.character_photo["zyemio"],
            anchor="s",
            tags="character"
        )

        self.gigao_id = self.canvas.create_image(
            int(w * 0.84),
            int(h * 0.96),
            image=self.character_photo["gigao"],
            anchor="s",
            tags="character"
        )
    

    def show_loading_bubble(self, speaker="zyemio", dots="..."):

        w = self.root.winfo_width()
        h = self.canvas.winfo_height()

        if speaker == "zyemio":
            x = int(w * 0.32)
        else:
            x = int(w * 0.68)

        y = int(h * 0.28)

        bubble_w = 130
        bubble_h = 70

        img = Image.new("RGBA", (bubble_w, bubble_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # なめらかな透明吹き出し
        draw.ellipse(
            (4, 4, bubble_w - 4, bubble_h - 4),
            fill=(255, 255, 255, 25),
            outline=(255, 255, 255, 220),
            width=3
        )

        # ...
        draw.text(
            (bubble_w // 2, bubble_h // 2 - 6),
            dots,
            fill=(255, 255, 255, 230),
            font=self.dot_font,
            anchor="mm"
        )

        photo = ImageTk.PhotoImage(img)
        self.bubble_photos.append(photo)

        self.canvas.create_image(
            x,
            y,
            image=photo,
            anchor="center",
            tags="bubble"
        )

        

    def animate_loading(self, step=0):

        if not self.loading_animation_running:
            self.canvas.delete("bubble")
            return
        
        self.canvas.delete("bubble")
        self.bubble_photos.clear()

        dots_list = ["   ",".  ", ".. ", "..."]
        dots = dots_list[step % 4]

        self.show_loading_bubble("zyemio", dots)
        self.show_loading_bubble("gigao", dots)

        self.root.after(
            400,
            lambda: self.animate_loading(step + 1)
        )

    def split_text_lines(self, text, max_chars=24):
        """
        吹き出し用の改行処理。
        「、」「。」ですぐ改行しすぎると文章が細切れになるので、
        ある程度たまってから区切る。
        """
        lines = []
        current = ""

        for ch in text:
            current += ch

            should_break = False

            if ch == "\n":
                should_break = True
            elif len(current) >= max_chars:
                should_break = True
            elif ch in "。！？" and len(current) >= 8:
                should_break = True
            elif ch == "、" and len(current) >= 16:
                should_break = True

            if should_break:
                if current.strip():
                    lines.append(current.strip())
                current = ""

        if current.strip():
            lines.append(current.strip())

        return lines

    def wrap_text(self, text, max_chars=24, max_lines=4):
        lines = self.split_text_lines(text, max_chars=max_chars)
        return "\n".join(lines[:max_lines])

    def get_page_line_count(self, text):
        lines = self.split_text_lines(text, max_chars=self.speech_line_chars)
        return len(lines)

    def should_switch_speech_page(self, text, next_char):
        """
        吹き出し切り替え判定。
        - 5行に到達したら強制切替
        - 3行目以降で「。」「、」「！」「？」が来たら、区切りが良いので切替
        """
        if not text:
            return False

        line_count = self.get_page_line_count(text)

        if line_count >= self.speech_page_line_limit:
            return True

        if line_count >= self.speech_switch_after_lines and next_char in "。、！？":
            return True

        return False

    def switch_speech_page(self):
        """
        吹き出しを 1 → 2 → 3 の順で増やす。
        3個目まで表示した状態で、さらに次の吹き出しが必要になったら、
        次の文字を出す直前に1〜3をまとめて消して、1個目から再開する。
        """
        old_slot = self.speech_active_slot

        if old_slot >= 2:
            # ここではまだ消さない。
            # 次の文字が来たタイミングでまとめて消す。
            self.speech_pending_clear = True
            return

        new_slot = old_slot + 1
        self.speech_active_slot = new_slot
        self.speech_pages[new_slot] = ""
        self.canvas.delete(f"speech_{new_slot}")

    def schedule_old_speech_delete_if_needed(self):
        """
        新しい吹き出しが出たら、古い吹き出しはすぐ消す。
        ログ欄があるので、吹き出しは「今しゃべっている部分」だけにする。
        """
        old_slot = 1 - self.speech_active_slot

        if not self.speech_pages[old_slot]:
            return

        self.delete_old_speech_page(old_slot)

    def delete_old_speech_page(self, slot):
        self.canvas.delete(f"speech_{slot}")
        self.speech_pages[slot] = ""
        self.speech_delete_after_id = None

    def show_speech_bubble(self, text, speaker="zyemio", slot=0):
        self.canvas.delete(f"speech_{slot}")

        if not text.strip():
            return

        w = self.root.winfo_width()
        h = self.canvas.winfo_height()

        # 吹き出しサイズは1・2・3で統一
        bubble_w = int(w * 0.36)
        bubble_h = 150

        # 1個目の基準座標
        # xを増やすと右へ、yを増やすと下へ移動
        if speaker == "zyemio":
            base_x = int(w * 0.42)
            base_y = int(h * 0.20)
            mirror = False

            # 手書き図イメージ：
            # 1個目 → 2個目は斜め右下
            # 2個目 → 3個目は斜め左下
            offset_list = [
                (0, 0),
                (int(bubble_w * 0.25), int(bubble_h * 0.65)),
                (int(bubble_w * 0.05), int(bubble_h * 1.30)),
            ]

        elif speaker == "gigao":
            base_x = int(w * 0.58)
            base_y = int(h * 0.20)
            mirror = True

            # ギガおは左右反転：
            # 1個目 → 2個目は斜め左下
            # 2個目 → 3個目は斜め右下
            offset_list = [
                (0, 0),
                (-int(bubble_w * 0.25), int(bubble_h * 0.65)),
                (-int(bubble_w * 0.05), int(bubble_h * 1.30)),
            ]

        else:
            base_x = int(w * 0.50)
            base_y = int(h * 0.20)
            mirror = False
            offset_list = [
                (0, 0),
                (int(bubble_w * 0.35), int(bubble_h * 0.72)),
                (0, int(bubble_h * 1.44)),
            ]

        slot = min(slot, 2)
        x = base_x + offset_list[slot][0]
        y = base_y + offset_list[slot][1]

        # 1個目だけしっぽあり、2個目以降はしっぽなし
        base_img = self.bubble_tail_img if slot == 0 else self.bubble_plain_img

        cache_key = (slot, bubble_w, bubble_h, mirror)

        if cache_key not in self.resized_bubble_cache:
            img_base = ImageOps.mirror(base_img) if mirror else base_img
            self.resized_bubble_cache[cache_key] = img_base.resize(
                (bubble_w, bubble_h),
                Image.Resampling.LANCZOS
            )

        img = self.resized_bubble_cache[cache_key].copy()
        draw = ImageDraw.Draw(img)

        text = self.wrap_text(
            text,
            max_chars=self.speech_line_chars,
            max_lines=self.speech_page_line_limit
        )

        # 文字座標。画像内の左上基準。
        # 文字が左すぎる/上すぎる場合は 0.12 / 0.20 を調整。
        text_x = int(bubble_w * 0.12)
        text_y = int(bubble_h * 0.20)

        draw.multiline_text(
            (text_x, text_y),
            text,
            fill=(255, 255, 255, 240),
            font=self.speech_font,
            anchor="la",
            align="left",
            spacing=8
        )

        self.speech_photos[slot] = ImageTk.PhotoImage(img)

        self.canvas.create_image(
            x,
            y,
            image=self.speech_photos[slot],
            anchor="center",
            tags=("speech", f"speech_{slot}")
        )

    def update_speech_bubbles(self, bubble_text, speaker):
        if bubble_text is None:
            return

        bubble_text = bubble_text.replace("【じぇみお】", "")
        bubble_text = bubble_text.replace("【ギガお】", "")
        bubble_text = bubble_text.strip()

        if bubble_text.startswith("【"):
            return

        # 話者が切り替わった時など、現在の文章が短くなったら初期化
        if len(bubble_text) < len(self.speech_previous_text):
            self.speech_previous_text = ""
            self.speech_pages = ["", "", ""]
            self.speech_photos = [None, None, None]
            self.speech_active_slot = 0
            self.speech_pending_clear = False
            self.canvas.delete("speech")

        added_text = bubble_text[len(self.speech_previous_text):]
        self.speech_previous_text = bubble_text

        for ch in added_text:
            # 3個目まで出した後、さらに続きが来たら、ここでまとめて消す
            if self.speech_pending_clear:
                self.canvas.delete("speech")
                self.speech_pages = ["", "", ""]
                self.speech_photos = [None, None, None]
                self.speech_active_slot = 0
                self.speech_pending_clear = False

            # 現在の吹き出しに1文字追加
            self.speech_pages[self.speech_active_slot] += ch

            self.show_speech_bubble(
                self.speech_pages[self.speech_active_slot],
                speaker,
                self.speech_active_slot
            )

            # 古い吹き出しは消さない。1・2・3を同時に残す。

            # 行数上限、または3行目以降の句読点で次の吹き出しへ
            if self.should_switch_speech_page(self.speech_pages[self.speech_active_slot], ch):
                self.switch_speech_page()


    def set_expression(self, char, emotion,speaker=None):
        if char == "zyemio":
            self.current_jemio = emotion
        elif char == "gigao":
            self.current_gigao = emotion

        self.show_characters(self.current_jemio, self.current_gigao, speaker=speaker)

    def reset_expressions(self, event=None):
        text = self.input_box.get("1.0", tk.END).strip()

        if text and self.last_input_empty and not self.is_busy:
            self.current_jemio = "normal"
            self.current_gigao = "normal"
            self.show_characters("normal", "normal")

        self.last_input_empty = (text == "")

    def parse_ai_tags(self, text):
        speaker = None
        emotion = "normal"

        if "[speaker=zyemio]" in text:
            speaker = "zyemio"
        elif "[speaker=gigao]" in text:
            speaker = "gigao"

        if "[emotion=happy]" in text:
            emotion = "happy"
        elif "[emotion=angry]" in text:
            emotion = "angry"
        elif "[emotion=cry]" in text:
            emotion = "cry"
        elif "[emotion=surprise]" in text:
            emotion = "surprise"
        elif "[emotion=thinking]" in text:
            emotion = "thinking"
        elif "[emotion=normal]" in text:
            emotion = "normal"

        clean_text = text
        clean_text = clean_text.replace("[speaker=zyemio]", "")
        clean_text = clean_text.replace("[speaker=gigao]", "")
        clean_text = clean_text.replace("[emotion=happy]", "")
        clean_text = clean_text.replace("[emotion=angry]", "")
        clean_text = clean_text.replace("[emotion=cry]", "")
        clean_text = clean_text.replace("[emotion=surprise]", "")
        clean_text = clean_text.replace("[emotion=thinking]", "")
        clean_text = clean_text.replace("[emotion=normal]", "")
        clean_text = clean_text.strip()

        return speaker, emotion, clean_text

    def extract_first_speech(self, text):
        text = text.strip()

        speaker = self.detect_speaker(text)

        if speaker == "zyemio":
            start_name = "【じぇみお】"
            other_name = "【ギガお】"
        elif speaker == "gigao":
            start_name = "【ギガお】"
            other_name = "【じぇみお】"
        else:
            return None, text

        start = text.find(start_name)
        if start != -1:
            text = text[start + len(start_name):]

        other = text.find(other_name)
        if other != -1:
            text = text[:other]

        text = text.strip()

        return speaker, text

    def extract_current_speech(self, text):
        last_jemio = text.rfind("【じぇみお】")
        last_gigao = text.rfind("【ギガお】")

        if last_jemio == -1 and last_gigao == -1:
            return None, text.strip()

        if last_jemio > last_gigao:
            speaker = "zyemio"
            start = last_jemio + len("【じぇみお】")
        else:
            speaker = "gigao"
            start = last_gigao + len("【ギガお】")

        current = text[start:]

        # 次の話者名・途中の話者名が出てきたら、吹き出しには出さない
        markers = [
            "【じぇみお】", "【ギガお】",
            "【", "【じ", "【じぇ", "【じぇみ", "【じぇみお",
            "【ギ", "【ギガ", "【ギガお"
        ]

        for marker in markers:
            pos = current.find(marker)
            if pos != -1:
                current = current[:pos]
                break

        clean = current.strip()

        if clean.startswith("【"):
            return speaker, ""

        return speaker, clean


    def detect_speaker(self, text):
        stripped = text.strip()

        if stripped.startswith("【じぇみお】"):
            return "zyemio"
        if stripped.startswith("【ギガお】"):
            return "gigao"

        first_jemio = stripped.find("【じぇみお】")
        first_gigao = stripped.find("【ギガお】")

        if first_jemio == -1 and first_gigao == -1:
            return None
        if first_jemio == -1:
            return "gigao"
        if first_gigao == -1:
            return "zyemio"

        return "zyemio" if first_jemio < first_gigao else "gigao"

    def detect_emotion(self, text):
        if any(word in text for word in ["！？", "驚", "まじ", "ヤバ", "えっ"]):
            return "surprise"
        if any(word in text for word in ["つら", "泣", "無理", "悲", "しんど"]):
            return "cry"
        if any(word in text for word in ["草", "よし", "いい", "勝ち", "できた", "成功"]):
            return "happy"
        return "angry"


    def open_jp_input(self):
        user_input = simpledialog.askstring("通信ゲート", "日本語を入力してくれ:", parent=self.root)
        if user_input:
            self.input_box.delete("1.0", tk.END)
            self.input_box.insert("1.0", user_input)
            self.send_message()

    def quick_send(self, text):
        if self.is_busy:
            return
        self.input_box.delete("1.0", tk.END)
        self.input_box.insert("1.0", text)
        self.send_message()


    def update_log_typing(self, text, index=0, on_complete=None):
        if index == 0:
            self.current_typing_text = text

            self.canvas.delete("speech")
            self.speech_pages = ["", "", ""]
            self.speech_photos = [None, None, None]
            self.speech_active_slot = 0
            self.speech_pending_clear = False
            self.speech_previous_text = ""
            self.speech_delete_after_id = None

            self.log_box.config(state=tk.NORMAL)

            if not self.history_visible:
                self.log_box.delete("1.0", tk.END)

            self.log_box.insert(tk.END, " ")
            self.log_box.config(state=tk.DISABLED)

        if index < len(text):
            current_text = text[:index + 1]
            bubble_speaker, bubble_text = self.extract_current_speech(current_text)

            if bubble_text:
                self.update_speech_bubbles(bubble_text, bubble_speaker)

            if current_text.endswith("【じぇみお】"):
                self.show_characters(self.current_jemio, self.current_gigao, speaker="zyemio")

            elif current_text.endswith("【ギガお】"):
                self.show_characters(self.current_jemio, self.current_gigao, speaker="gigao")
            self.log_box.config(state=tk.NORMAL)
            self.log_box.insert(tk.END, text[index])
            self.log_box.see(tk.END)
            self.log_box.config(state=tk.DISABLED)

            self.root.after(55, lambda: self.update_log_typing(text, index + 1, on_complete))     #文字出力
        else:
            self.log_box.config(state=tk.NORMAL)
            self.log_box.insert(tk.END, "\n")
            self.log_box.config(state=tk.DISABLED)

            # 文字送りが全部終わったタイミングで履歴に保存
            self.history_logs.append(text)

            if on_complete:
                self.root.after(1200, on_complete)

    def toggle_history(self):
        self.history_visible = not self.history_visible

        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete("1.0", tk.END)

        if self.history_visible:
            self.history_btn.configure(text="▲")
            for log in self.history_logs:
                self.log_box.insert(tk.END, log + "\n")
        else:
            self.history_btn.configure(text="▼")
            if self.history_logs:
                self.log_box.insert(tk.END, self.history_logs[-1] + "\n")

        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)

    def update_log(self, text):
        self.history_logs.append(text)

        self.log_box.config(state=tk.NORMAL)

        if self.history_visible:
            self.log_box.insert(tk.END, text + "\n")
        else:
            self.log_box.delete("1.0", tk.END)
            self.log_box.insert(tk.END, text + "\n")

        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)

    def on_resize(self, event):
        if not os.path.exists(FINAL_IMG): return
        w = self.root.winfo_width()
        available_h = self.root.winfo_height() - 170
        h = min(int(w / self.ratio), available_h)
        
        self.canvas.config(width=w, height=h)
        img_raw = Image.open(FINAL_IMG).resize((w, h), Image.Resampling.LANCZOS)
        self.bg_photo = ImageTk.PhotoImage(img_raw)
        self.canvas.delete("bg")
        self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw", tags="bg")
        self.show_characters(self.current_jemio, self.current_gigao)

    def send_message_safe(self, event=None):
        self.send_message()
        return "break"

    def insert_newline(self, event):
        self.input_box.insert(tk.INSERT, "\n")
        return "break"

    def finish_response(self):
        self.loading_animation_running = False
        self.canvas.delete("bubble")
        self.is_busy = False
        self.send_btn.configure(state="normal")
        self.weather_btn.configure(state="normal")

        self.current_jemio = "normal"
        self.current_gigao = "normal"
        self.show_characters("normal", "normal")
        

    def send_message(self, event=None):
    
        if self.is_busy:
            return

        message = self.input_box.get("1.0", "end-1c").strip()

        if not message:
            return

        self.is_busy = True

        self.send_btn.configure(state="disabled")
        self.weather_btn.configure(state="disabled")
        
        self.input_box.delete("1.0", "end")
        self.update_log(f"\n俺: {message}")
        self.current_jemio = "thinking"
        self.current_gigao = "thinking"
        self.show_characters("thinking", "thinking",speaker="none")
        self.loading_animation_running = True
        self.animate_loading()
        self.root.update()
        
        threading.Thread(
            target=self.call_ai_stream,
            args=(message,),
            daemon=True
        ).start()

    def call_ai_stream(self, message):
        try:
            start_time = time.time()

            response = self.chat.send_message_stream(message)

            header_buffer = ""
            body_started = False
            full_text = ""

            first_chunk_time = None
            chunk_count = 0

            for chunk in response:

                if first_chunk_time is None:
                    first_chunk_time = time.time()

                chunk_count += 1

                text = chunk.text

                if not text:
                    continue

                if not body_started:

                    header_buffer += text

                    if "\n" in header_buffer:

                        first_line, rest = header_buffer.split("\n", 1)

                        speaker, emotion, _ = self.parse_ai_tags(first_line)

                        if speaker == "zyemio":
                            self.current_jemio = emotion
                            self.current_gigao = "normal"

                        elif speaker == "gigao":
                            self.current_jemio = "normal"
                            self.current_gigao = emotion

                        else:
                            self.current_jemio = emotion
                            self.current_gigao = emotion

                        self.root.after(
                            0,
                            lambda s=speaker, je=self.current_jemio, gi=self.current_gigao:
                            self.start_stream_display(
                                je,
                                gi,
                                s
                            )
                        )

                        if rest:
                            self.root.after(
                                0,
                                lambda t=rest, s=speaker:
                                self.enqueue_stream_text(t, s)
                            )

                        body_started = True

                else:

                    full_text += text

                    self.root.after(
                        0,
                        lambda t=text:
                        self.enqueue_stream_text(t)
                    )

            end_time = time.time()

            self.root.after(
                0,
                self.mark_stream_done
            )

        except Exception as e:

            print("Geminiエラー:", e)

            self.root.after(
                0,
                lambda: self.handle_ai_error(str(e))
            )

    def start_stream_display(self, jemio_emotion, gigao_emotion, speaker):
        
        """
        ローディング吹き出しを消して、ストリーミング文字送りを開始する準備。
        """
        self.loading_animation_running = False
        self.canvas.delete("bubble")

        self.current_jemio = jemio_emotion
        self.current_gigao = gigao_emotion
        self.show_characters(self.current_jemio, self.current_gigao, speaker=speaker)

        self.canvas.delete("speech")
        self.speech_pages = ["", "", ""]
        self.speech_photos = [None, None, None]
        self.speech_active_slot = 0
        self.speech_pending_clear = False
        self.speech_previous_text = ""
        self.speech_delete_after_id = None

        self.stream_queue = []
        self.stream_display_text = ""
        self.stream_full_text = ""
        self.stream_default_speaker = speaker
        self.stream_api_done = False
        self.stream_typing_running = False
        self.stream_finished_once = False

        self.log_box.config(state=tk.NORMAL)
        if not self.history_visible:
            self.log_box.delete("1.0", tk.END)
        self.log_box.config(state=tk.DISABLED)


    def enqueue_stream_text(self, text, default_speaker=None):
        """
        APIから来た文字を画面表示キューへ積む。
        ここではまだ一括表示しない。
        """
        if default_speaker is not None:
            self.stream_default_speaker = default_speaker

        for ch in text:
            self.stream_queue.append(ch)
            self.stream_full_text += ch

        if not self.stream_typing_running:
            self.stream_typing_running = True
            self.type_next_stream_char()


    def type_next_stream_char(self):
        """
        キューから1文字ずつ取り出して、ログと吹き出しに表示する。
        """
        if not self.stream_queue:
            self.stream_typing_running = False

            if self.stream_api_done:
                self.finish_stream_response(self.stream_full_text)
            return

        ch = self.stream_queue.pop(0)
        self.stream_display_text += ch

        bubble_speaker, bubble_text = self.extract_current_speech(self.stream_display_text)
        if bubble_speaker is None:
            bubble_speaker = self.stream_default_speaker

        if bubble_text:
            self.update_speech_bubbles(bubble_text, bubble_speaker)

        if self.stream_display_text.endswith("【じぇみお】"):
            self.show_characters(self.current_jemio, self.current_gigao, speaker="zyemio")
        elif self.stream_display_text.endswith("【ギガお】"):
            self.show_characters(self.current_jemio, self.current_gigao, speaker="gigao")

        self.log_box.config(state=tk.NORMAL)
        self.log_box.insert(tk.END, ch)
        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)

        self.root.after(35, self.type_next_stream_char)


    def mark_stream_done(self):
        """
        APIからの受信完了。文字送りキューが空になってから終了処理する。
        """
        self.stream_api_done = True
        if not self.stream_typing_running and not self.stream_queue:
            self.finish_stream_response(self.stream_full_text)


    def finish_stream_response(self, full_text):
        
        """
        ストリーミング文字送りが全部終わった後の後処理。
        """
        if self.stream_finished_once:
            return
        self.stream_finished_once = True

        if full_text.strip():
            self.history_logs.append(full_text)

        self.log_box.config(state=tk.NORMAL)
        self.log_box.insert(tk.END, "\n")
        self.log_box.config(state=tk.DISABLED)

        self.root.after(1200, self.finish_response)


    def handle_ai_response(self, full_text):
        self.loading_animation_running = False
        self.canvas.delete("bubble")

        speaker, emotion, full_text = self.parse_ai_tags(full_text)

        if speaker == "zyemio":
            self.current_jemio = emotion
            self.current_gigao = "normal"
        elif speaker == "gigao":
            self.current_jemio = "normal"
            self.current_gigao = emotion
        else:
            self.current_jemio = emotion
            self.current_gigao = emotion

        self.show_characters(
            self.current_jemio,
            self.current_gigao,
            speaker=speaker
        )

        self.update_log_typing(
            full_text,
            on_complete=self.finish_response
        )

    def handle_ai_error(self, message):
        self.loading_animation_running = False
        self.canvas.delete("bubble")
        self.update_log(f"（エラーだぜ: {message}）")
        self.finish_response()
    

def prepare_wallpaper():
    if os.path.exists(INPUT_IMG):
        img = Image.open(INPUT_IMG)
        w, h = img.size
        target_ratio = 16 / 9
        new_h = w / target_ratio
        top = (h - new_h) / 2
        bottom = (h + new_h) / 2
        img.crop((0, top, w, bottom)).save(FINAL_IMG, "PNG")

if __name__ == "__main__":
    prepare_wallpaper()
    root = tk.Tk()
    app = HimitsuKichiApp(root)
    root.mainloop()