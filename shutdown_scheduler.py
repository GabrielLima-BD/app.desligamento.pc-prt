import os
import json
import tkinter as tk
from tkinter import messagebox
import subprocess
import datetime
import time


# Tentativa de importar customtkinter; se não existir, mostramos instruções amigáveis e encerramos.
USING_CUSTOMTK = True
try:
    import customtkinter as ctk
except ModuleNotFoundError:
    USING_CUSTOMTK = False
    # Garantir que ao menos o tkinter esteja disponível para mostrar a mensagem
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Dependência ausente",
        "A biblioteca 'customtkinter' não está instalada.\n\nInstale com:\n  pip install customtkinter\n\nou\n  pip install -r requirements.txt\n\nDepois execute novamente o programa.")
    root.destroy()
    raise SystemExit(1)


class ShutdownScheduler(ctk.CTk):
    """Aplicativo para agendar/desagendar shutdown no Windows usando `shutdown -s -t` e `shutdown -a`.

    Oferece opções por segundos, minutos, horas ou um horário específico (HH:MM).
    Converte tudo para segundos porque o comando do Windows espera segundos.
    """

    def __init__(self):
        super().__init__()
        self.title("Agendador de Desligamento")
        self.geometry("480x340")
        self.resizable(False, False)

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # Estado
        self.countdown_job = None
        self.remaining_seconds = 0

        # Caminho do arquivo de configuração
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.json')

        # Widgets
        self._build_ui()

        # Carregar configuração se existir
        self.load_config()

        # Se habilitado para diário, agenda um desligamento para a próxima ocorrência
        self.schedule_daily_if_enabled()

    def _build_ui(self):
        pad = 12

        frame = ctk.CTkFrame(self)
        frame.pack(padx=pad, pady=pad, fill="both", expand=True)

        title = ctk.CTkLabel(frame, text="Agendar desligamento do Windows", font=ctk.CTkFont(size=16, weight="bold"))
        title.pack(pady=(0, 10))

        # Modo: segundos/minutos/horas/horário
        self.mode_var = tk.StringVar(value="Minutos")
        mode_menu = ctk.CTkOptionMenu(frame, values=["Segundos", "Minutos", "Horas", "Horário (HH:MM)"], variable=self.mode_var, command=self.on_mode_change)
        mode_menu.pack(pady=(0, 8))

        # Entrada genérica (número)
        self.value_entry = ctk.CTkEntry(frame, placeholder_text="Valor (ex: 15)")
        self.value_entry.pack(pady=(0, 8))

        # Entrada para horário específico
        self.time_entry = ctk.CTkEntry(frame, placeholder_text="HH:MM (24h)")

        # Opções de agendamento diário
        self.daily_var = tk.BooleanVar(value=False)
        daily_frame = ctk.CTkFrame(frame)
        daily_frame.pack(fill="x", pady=(4, 4))
        self.daily_check = ctk.CTkCheckBox(daily_frame, text="Agendar diariamente (apenas para Horário)", variable=self.daily_var)
        self.daily_check.pack(side="left", padx=(0, 6))
        save_cfg_btn = ctk.CTkButton(daily_frame, text="Salvar Configuração", width=160, command=self.on_save_config)
        save_cfg_btn.pack(side="right")

        # Botões
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(pady=(6, 6), fill="x")

        schedule_btn = ctk.CTkButton(btn_frame, text="Agendar Desligamento", command=self.on_schedule)
        schedule_btn.pack(side="left", expand=True, padx=(6, 3), pady=6)

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancelar Desligamento", fg_color="#b22222", hover_color="#ff3333", command=self.on_cancel)
        cancel_btn.pack(side="right", expand=True, padx=(3, 6), pady=6)

        # Label com o total de segundos calculado e contagem regressiva
        self.info_label = ctk.CTkLabel(frame, text="Tempo convertido: - ")
        self.info_label.pack(pady=(6, 0))

        # Estimativa de horário de desligamento
        self.estimated_label = ctk.CTkLabel(frame, text="Estimativa de desligamento: -")
        self.estimated_label.pack(pady=(2, 0))

        self.countdown_label = ctk.CTkLabel(frame, text="Contagem: - ")
        self.countdown_label.pack(pady=(4, 0))

        # Nota
        note = ctk.CTkLabel(frame, text="OBS: O comando do Windows pode precisar de privilégios de administrador.")
        note.pack(side="bottom", pady=(8, 0))

        self.on_mode_change(self.mode_var.get())

        # Bindings de scroll para ajustar valores com o mouse
        # Windows: <MouseWheel>, event.delta (multiples of 120); Linux/X11 usar Button-4/5 se necessário
        self.value_entry.bind('<MouseWheel>', self.on_mouse_wheel)
        self.time_entry.bind('<MouseWheel>', self.on_mouse_wheel)

    def on_mode_change(self, mode):
        # Mostrar/ocultar campos conforme modo
        if mode == "Horário (HH:MM)":
            try:
                self.value_entry.pack_forget()
            except Exception:
                pass
            self.time_entry.pack(pady=(0, 8))
        else:
            try:
                self.time_entry.pack_forget()
            except Exception:
                pass
            self.value_entry.pack(pady=(0, 8))

        # Atualiza preview sempre que o modo muda
        self.update_converted_seconds()

    def on_schedule(self):
        mode = self.mode_var.get()
        try:
            if mode == "Horário (HH:MM)":
                text = self.time_entry.get().strip()
                if not text:
                    messagebox.showerror("Erro", "Informe o horário no formato HH:MM")
                    return
                seconds = self._seconds_until_time(text)
                if seconds <= 0:
                    messagebox.showerror("Erro", "Horario inválido ou igual ao atual")
                    return
            else:
                text = self.value_entry.get().strip()
                if not text:
                    messagebox.showerror("Erro", "Informe um valor numérico")
                    return
                val = int(float(text))
                if val < 0:
                    messagebox.showerror("Erro", "Valor deve ser positivo")
                    return
                if mode == "Segundos":
                    seconds = val
                elif mode == "Minutos":
                    seconds = val * 60
                elif mode == "Horas":
                    seconds = val * 3600
                else:
                    seconds = val

        except ValueError:
            messagebox.showerror("Erro", "Valor inválido (digite apenas números ou HH:MM)")
            return

        # Atualizar label e executar comando
        self.info_label.configure(text=f"Tempo convertido: {seconds} segundos")
        # Mostrar estimativa horária
        try:
            target = (datetime.datetime.now() + datetime.timedelta(seconds=seconds)).strftime('%H:%M')
            self.estimated_label.configure(text=f"Estimativa de desligamento: {target}")
        except Exception:
            self.estimated_label.configure(text="Estimativa de desligamento: -")
        self._run_shutdown_command(seconds)

        # Se o usuário quer agendar diariamente e escolheu Horário, salvar automaticamente
        if self.daily_var.get() and mode == "Horário (HH:MM)":
            try:
                text = self.time_entry.get().strip()
                self.save_config({'daily_time': text, 'daily_enabled': True})
            except Exception:
                pass

    def _seconds_until_time(self, hhmm: str) -> int:
        try:
            parts = hhmm.split(":")
            if len(parts) != 2:
                raise ValueError
            h = int(parts[0])
            m = int(parts[1])
            if not (0 <= h < 24 and 0 <= m < 60):
                raise ValueError
        except Exception:
            raise ValueError("Formato de horário inválido. Use HH:MM (24h).")

        now = datetime.datetime.now()
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            target = target + datetime.timedelta(days=1)
        delta = target - now
        return int(delta.total_seconds())

    def _run_shutdown_command(self, seconds: int):
        # Executa o comando shutdown -s -t <seconds>
        try:
            completed = subprocess.run(["shutdown", "-s", "-t", str(int(seconds))], capture_output=True, text=True)
            if completed.returncode == 0:
                messagebox.showinfo("Agendado", f"Desligamento agendado em {seconds} segundos.")
            else:
                messagebox.showwarning("Comando retornou erro", f"O comando retornou código {completed.returncode}.\nSaída: {completed.stdout}\nErro: {completed.stderr}\nTente executar o programa como administrador se necessário.")

        except FileNotFoundError:
            messagebox.showerror("Erro", "Comando 'shutdown' não encontrado. Este script foi feito para Windows.")
            return
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao executar comando: {e}")
            return

        # Iniciar contagem local (apenas visual)
        self._start_local_countdown(seconds)
        # Atualiza estimativa caso não tenha sido atualizada
        try:
            target = (datetime.datetime.now() + datetime.timedelta(seconds=seconds)).strftime('%H:%M')
            self.estimated_label.configure(text=f"Estimativa de desligamento: {target}")
        except Exception:
            pass

    def _start_local_countdown(self, seconds: int):
        if self.countdown_job is not None:
            try:
                self.after_cancel(self.countdown_job)
            except Exception:
                pass
            self.countdown_job = None

        self.remaining_seconds = int(seconds)
        self._update_countdown_label()

    def _update_countdown_label(self):
        if self.remaining_seconds <= 0:
            self.countdown_label.configure(text="Contagem: 0s")
            self.countdown_job = None
            return

        hrs, rem = divmod(self.remaining_seconds, 3600)
        mins, secs = divmod(rem, 60)
        self.countdown_label.configure(text=f"Contagem: {hrs}h {mins}m {secs}s")
        self.remaining_seconds -= 1
        self.countdown_job = self.after(1000, self._update_countdown_label)

    def on_cancel(self):
        try:
            completed = subprocess.run(["shutdown", "-a"], capture_output=True, text=True)
            if completed.returncode == 0:
                messagebox.showinfo("Cancelado", "Solicitação de desligamento cancelada (shutdown -a).")
            else:
                messagebox.showwarning("Aviso", f"shutdown -a retornou código {completed.returncode}.\nSaída: {completed.stdout}\nErro: {completed.stderr}")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao executar 'shutdown -a': {e}")
            return

        if self.countdown_job is not None:
            try:
                self.after_cancel(self.countdown_job)
            except Exception:
                pass
            self.countdown_job = None
            self.countdown_label.configure(text="Contagem: -")
            self.info_label.configure(text="Tempo convertido: - ")

    def on_mouse_wheel(self, event):
        mode = self.mode_var.get()
        # On Windows, event.delta is multiple of 120; positive = up, negative = down
        sign = 1 if event.delta > 0 else -1

        if mode == "Horário (HH:MM)":
            txt = self.time_entry.get().strip()
            if not txt:
                h, m = 0, 0
            else:
                try:
                    parts = txt.split(":")
                    h = int(parts[0])
                    m = int(parts[1])
                except Exception:
                    h, m = 0, 0
            m += 15 * sign
            # Normalize
            while m >= 60:
                h = (h + 1) % 24
                m -= 60
            while m < 0:
                h = (h - 1) % 24
                m += 60
            self.time_entry.delete(0, tk.END)
            self.time_entry.insert(0, f"{h:02d}:{m:02d}")
        else:
            txt = self.value_entry.get().strip()
            try:
                current = int(float(txt)) if txt else 0
            except Exception:
                current = 0

            if mode == "Segundos":
                delta = 150 * sign
                current = max(0, current + delta)
            elif mode == "Minutos":
                delta = 15 * sign
                current = max(0, current + delta)
            elif mode == "Horas":
                delta = 1 * sign
                current = max(0, current + delta)

            self.value_entry.delete(0, tk.END)
            self.value_entry.insert(0, str(current))

        self.update_converted_seconds()

    def update_converted_seconds(self):
        mode = self.mode_var.get()
        try:
            if mode == "Horário (HH:MM)":
                txt = self.time_entry.get().strip()
                if not txt:
                    self.info_label.configure(text="Tempo convertido: - ")
                    return
                seconds = self._seconds_until_time(txt)
            else:
                txt = self.value_entry.get().strip()
                if not txt:
                    self.info_label.configure(text="Tempo convertido: - ")
                    return
                val = int(float(txt))
                if mode == "Segundos":
                    seconds = val
                elif mode == "Minutos":
                    seconds = val * 60
                elif mode == "Horas":
                    seconds = val * 3600
                else:
                    seconds = val
            self.info_label.configure(text=f"Tempo convertido: {seconds} segundos")
            try:
                target = (datetime.datetime.now() + datetime.timedelta(seconds=seconds)).strftime('%H:%M')
                self.estimated_label.configure(text=f"Estimativa de desligamento: {target}")
            except Exception:
                self.estimated_label.configure(text="Estimativa de desligamento: -")
        except Exception:
            self.info_label.configure(text="Tempo convertido: - ")

    def on_save_config(self):
        cfg = {'daily_enabled': bool(self.daily_var.get())}
        if self.mode_var.get() == "Horário (HH:MM)":
            txt = self.time_entry.get().strip()
            try:
                _ = self._seconds_until_time(txt)
                cfg['daily_time'] = txt
            except Exception:
                messagebox.showerror("Erro", "Horário inválido. Use HH:MM antes de salvar.")
                return
        else:
            cfg['daily_time'] = cfg.get('daily_time', '')

        self.save_config(cfg)
        messagebox.showinfo("Salvo", "Configuração salva em config.json")
        # atualizar estimativa visual
        self.update_converted_seconds()

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                daily_time = cfg.get('daily_time')
                daily_enabled = bool(cfg.get('daily_enabled', False))
                self.daily_var.set(daily_enabled)
                if daily_time:
                    self.mode_var.set("Horário (HH:MM)")
                    self.on_mode_change(self.mode_var.get())
                    self.time_entry.delete(0, tk.END)
                    self.time_entry.insert(0, daily_time)
                    try:
                        seconds = self._seconds_until_time(daily_time)
                        self.info_label.configure(text=f"Tempo convertido: {seconds} segundos")
                        try:
                            target = (datetime.datetime.now() + datetime.timedelta(seconds=seconds)).strftime('%H:%M')
                            self.estimated_label.configure(text=f"Estimativa de desligamento: {target} (diário)")
                        except Exception:
                            pass
                    except Exception:
                        pass
        except Exception:
            pass

    def save_config(self, cfg: dict):
        data = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data.update(cfg)
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar config: {e}")

    def schedule_daily_if_enabled(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                if cfg.get('daily_enabled') and cfg.get('daily_time'):
                    seconds = self._seconds_until_time(cfg['daily_time'])
                    self.info_label.configure(text=f"Tempo convertido: {seconds} segundos (agendado diariamente)")
                    self._run_shutdown_command(seconds)
        except Exception:
            pass


def _format_seconds(s):
    return int(s)


def main():
    app = ShutdownScheduler()
    app.mainloop()


if __name__ == "__main__":
    main()
