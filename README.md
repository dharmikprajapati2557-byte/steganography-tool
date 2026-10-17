# GhostPixel (stegtool): Step-by-Step Guide for Windows

GhostPixel hides secret text or files inside PNG/BMP images and plain text.
You can use it from a window (GUI) or from the command line.

---

## 1. What You Need (Requirements)

| Requirement | Why | Check it |
|---|---|---|
| Windows 10 or 11 | The steps below are written for Windows | Settings > System > About |
| Python 3.10 or newer | Runs the program | Open Command Prompt, type `python --version` |
| Internet connection | To download the packages | - |
| The project folder `stegtool` | Contains all the code | Should contain `run_gui.py`, `cli.py`, `requirements.txt` |

Packages installed automatically from `requirements.txt`:
- Pillow (images)
- numpy (math for images)
- cryptography (password encryption)
- customtkinter (the window design)
- tkinterdnd2 (drag and drop, optional)
- pytest (tests, optional)

---

## 2. Install Python (only if you don't have it)

1. Go to **python.org/downloads** and download the latest Python 3.
2. Run the installer.
3. **IMPORTANT:** On the first screen, tick the box **"Add python.exe to PATH"**.
4. Click **Install Now**.
5. When it finishes, close and reopen any open windows.

---

## 3. Open the Project Folder

1. Open **File Explorer** and go to the `stegtool` folder.
2. Click the address bar at the top, type `cmd`, and press **Enter**.
   A black Command Prompt window opens already inside the folder.

---

## 4. Create a Virtual Environment (recommended)

This keeps the project's packages separate from the rest of your computer.

Type this and press **Enter**:

```
python -m venv .venv
```

Then activate it:

```
.venv\Scripts\activate
```

You should now see `(.venv)` at the start of the line.

---

## 5. Install the Requirements

With `(.venv)` showing, type:

```
pip install -r requirements.txt
```

Wait until it finishes. The last line should say *Successfully installed...*.

---

## 6. Run the Program

### Option A: Graphical window (GUI)

```
python run_gui.py
```

A GhostPixel window opens with a sidebar: **Hide**, **Reveal**, **Analyze**, **Settings**, **About**.

### Option B: Command line

Hide a text message in an image:

```
python cli.py image-encode -i photo.png -o photo_stego.png -m "Meet at midnight" -p hunter2
```

Reveal the message:

```
python cli.py image-decode -i photo_stego.png -p hunter2
```

Check an image for hidden data:

```
python cli.py image-analyze -i photo_stego.png
```

Replace `photo.png` with your own image file name. Put the image in the `stegtool` folder first.

---

## 7. Run the Tests (optional)

```
python -m pytest -q
```

If all tests pass, the project works correctly.

---

## 8. Common Errors and Solutions

### Error: `'python' is not recognized as an internal or external command`
**Cause:** Python was not added to PATH.
**Solution:** Reinstall Python and tick **"Add python.exe to PATH"**. Or try `py --version` instead of `python`, and use `py` in place of `python` in every command.

### Error: `No module named customtkinter` (or `numpy`, `PIL`, `cryptography`)
**Cause:** The requirements were not installed, or the virtual environment is not active.
**Solution:** Make sure `(.venv)` shows in the window, then run:
```
pip install -r requirements.txt
```

### Error: `No module named tkinter`
**Cause:** The Python installation is missing the Tk part.
**Solution:** Run the Python installer again, choose **Modify**, and make sure **tcl/tk and IDLE** is ticked.

### Error: `pip is not recognized`
**Solution:** Use this instead:
```
python -m pip install -r requirements.txt
```

### Error: `tkinterdnd2` fails to install or drag and drop does not work
**Cause:** Drag and drop is optional.
**Solution:** Ignore it. Use the **Browse** buttons to choose files instead.

### Error: Image rejected or message not hidden properly (JPEG files)
**Cause:** JPEG compression destroys hidden data. Only PNG and BMP are accepted.
**Solution:** Save the image as **PNG** and use that file.

### Error: Hidden message is "incomplete" when revealing text
**Cause:** The text was copied through an app or website that removed invisible characters.
**Solution:** Copy the text in a plain editor like Notepad and save it as a file. Then reveal it from that file.

### Error: Wrong password or data cannot be read
**Cause:** The password is wrong, or the file was changed after hiding.
**Solution:** Check the password carefully. Make sure you use the exact image that was created.

### Problem: Message disappears after sending to WhatsApp, Instagram, or email
**Cause:** Apps compress images and remove hidden data.
**Solution:** Send the image as a **document/file**, not as a photo. Or copy the file another way, such as USB.

### Problem: Analyze says an image is "suspicious" but it has no message
**Cause:** The test is a guess. Noisy or synthetic images can look suspicious.
**Solution:** This is normal. The result is only a hint, not proof.

---

## 9. Important Notes

- Hiding data does not make it secret. Always use a password (`-p`) for private information.
- The original image is never overwritten. The result is saved as a new file.
- Your settings are saved in `C:\Users\YourName\.ghostpixel\config.json`.
- Use this tool for privacy, learning, watermarking, or CTF challenges only.

---

## 10. Quick Summary

1. Install Python (tick "Add to PATH").
2. Open the `stegtool` folder, type `cmd` in the address bar.
3. `python -m venv .venv` then `.venv\Scripts\activate`
4. `pip install -r requirements.txt`
5. `python run_gui.py`
