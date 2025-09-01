"""
table_extractor.py - זיהוי וחילוץ טבלאות מתקדם לחשבוניות
"""

import cv2
import numpy as np
import pytesseract
from typing import List, Tuple, Dict, Optional
import logging

class TableExtractor:
    """מחלקה לזיהוי וחילוץ טבלאות מתקדם"""
    
    def __init__(self):
        """אתחול מחלץ הטבלאות"""
        self.debug_mode = False
        
    def smart_rotation_correction(self, image: np.ndarray, progress_callback=None) -> np.ndarray:
        """תיקון סיבוב חכם - קודם 90° ואז זוויות קלות"""
        try:
            if progress_callback:
                progress_callback("בודק סיבובים של 90 מעלות...")
            
            # שלב 1: בדיקת סיבובים של 90 מעלות עם OSD
            rotated_image = self._try_osd_rotation(image, progress_callback)
            
            # שלב 2: אם לא היה סיבוב גדול, בדוק זוויות קלות
            if np.array_equal(rotated_image, image):  # לא השתנתה התמונה
                if progress_callback:
                    progress_callback("בודק זוויות קלות...")
                rotated_image = self._detect_skew_by_lines(image, progress_callback)
            
            return rotated_image
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"שגיאה בתיקון סיבוב: {str(e)}")
            return image
    
    def _try_osd_rotation(self, image: np.ndarray, progress_callback=None) -> np.ndarray:
        """ניסיון זיהוי סיבובים של 90 מעלות"""
        try:
            # המרה לRGB אם צריך
            if len(image.shape) == 2:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            else:
                rgb_image = image
                
            # זיהוי כיוון עם Tesseract
            osd_result = pytesseract.image_to_osd(
                rgb_image, 
                config='--psm 0 -c min_characters_to_try=5',
                output_type=pytesseract.Output.DICT
            )
            
            detected_angle = osd_result.get('rotate', 0)
            confidence = osd_result.get('orientation_conf', 0)
            
            if progress_callback:
                progress_callback(f"OSD זיהה: {detected_angle}° (ביטחון: {confidence:.1f})")
            
            # סיבוב רק עם ביטחון גבוה ולזוויות של 90°
            if confidence > 1.5 and abs(detected_angle) >= 90:
                if progress_callback:
                    progress_callback(f"מסובב תמונה ב-{detected_angle} מעלות...")
                
                import imutils
                rotated_image = imutils.rotate_bound(rgb_image, detected_angle)
                
                # המרה חזרה לגרייסקייל אם צריך
                if len(image.shape) == 2:
                    return cv2.cvtColor(rotated_image, cv2.COLOR_RGB2GRAY)
                else:
                    return rotated_image
            else:
                return image  # ללא שינוי
                
        except Exception as e:
            if progress_callback:
                progress_callback(f"OSD נכשל: {str(e)}")
            return image
    
    def _detect_skew_by_lines(self, image: np.ndarray, progress_callback=None) -> np.ndarray:
        """זיהוי זוויות קלות על בסיס קווים"""
        try:
            if progress_callback:
                progress_callback("מנסה זיהוי זוויות קלות על בסיס קווים...")
            
            # המרה לבינארי
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # בינאריזציה
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # זיהוי קווים עם Hough Transform
            edges = cv2.Canny(binary, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi/360, threshold=50)
            
            if lines is not None and len(lines) > 0:
                angles = []
                for line in lines[:10]:  # בדוק רק 10 קווים ראשונים
                    rho, theta = line[0]  # חילוץ נכון של הערכים
                    angle = (theta - np.pi/2) * 180 / np.pi
                    angles.append(angle)
                
                # מצא זווית חציונית
                median_angle = np.median(angles)
                
                # תקן רק זוויות קלות (לא 90 מעלות)
                if 0.5 < abs(median_angle) < 45:  # זוויות קלות בלבד
                    rotation_angle = -median_angle  # סיבוב הפוך
                    
                    if progress_callback:
                        progress_callback(f"זוהתה זווית קלה: {median_angle:.1f}°, מתקן...")
                    
                    import imutils
                    return imutils.rotate_bound(image, rotation_angle)
                
            if progress_callback:
                progress_callback("לא נמצאה זווית משמעותית")
            
            return image
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"שגיאה בזיהוי זוויות קלות: {str(e)}")
            return image
        
    def extract_table_data(self, image: np.ndarray, progress_callback=None) -> Dict:
        """חילוץ נתוני טבלה מתקדם מתמונה"""
        try:
            if progress_callback:
                progress_callback("מזהה מבנה טבלה...")
                
            # זיהוי מבנה הטבלה
            table_structure = self._detect_table_structure(image)
            
            if not table_structure:
                if progress_callback:
                    progress_callback("לא זוהתה טבלה - עובר למצב רגיל")
                return None
                
            if progress_callback:
                progress_callback("חולץ תאי טבלה...")
                
            # חילוץ תאים
            table_cells = self._extract_table_cells(image, table_structure)
            
            if progress_callback:
                progress_callback("מזהה מק\"טים...")
                
            # זיהוי מק"טים ספציפי
            item_codes = self._extract_item_codes(table_cells)
            
            return {
                "table_detected": True,
                "structure": table_structure,
                "cells": table_cells,
                "item_codes": item_codes,
                "method": "advanced_table_extraction"
            }
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"שגיאה בחילוץ טבלה: {str(e)}")
            return None
    
    def _detect_table_structure(self, image: np.ndarray) -> Optional[Dict]:
        """זיהוי מבנה הטבלה - קווים וזוויות"""
        try:
            # המרה לגרייסקייל אם צריך
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # שיפור ניגודיות לזיהוי קווים טוב יותר
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # זיהוי קווים אנכיים ואופקיים
            horizontal_lines = self._detect_horizontal_lines(enhanced)
            vertical_lines = self._detect_vertical_lines(enhanced)
            
            if len(horizontal_lines) < 2 or len(vertical_lines) < 2:
                return None
                
            # חישוב זווית הטיה
            table_angle = self._calculate_table_angle(horizontal_lines)
            
            # זיהוי אזור הטבלה
            table_bounds = self._find_table_bounds(horizontal_lines, vertical_lines)
            
            return {
                "horizontal_lines": horizontal_lines,
                "vertical_lines": vertical_lines, 
                "table_angle": table_angle,
                "table_bounds": table_bounds,
                "rows": len(horizontal_lines) - 1,
                "cols": len(vertical_lines) - 1
            }
            
        except Exception as e:
            logging.error(f"שגיאה בזיהוי מבנה טבלה: {str(e)}")
            return None
    
    def _detect_horizontal_lines(self, image: np.ndarray) -> List[Tuple]:
        """זיהוי קווים אופקיים"""
        # יצירת kernel אופקי
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        
        # זיהוי קווים אופקיים
        horizontal_lines_img = cv2.morphologyEx(image, cv2.MORPH_OPEN, horizontal_kernel)
        
        # זיהוי קווים עם Hough Transform
        edges = cv2.Canny(horizontal_lines_img, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=200, maxLineGap=10)
        
        horizontal_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # סינון קווים אופקיים (זווית קטנה)
                angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
                if angle < 15:  # קווים כמעט אופקיים
                    horizontal_lines.append((x1, y1, x2, y2))
        
        # מיון לפי Y (מלמעלה למטה)
        horizontal_lines.sort(key=lambda line: (line[1] + line[3]) / 2)
        
        return horizontal_lines
    
    def _detect_vertical_lines(self, image: np.ndarray) -> List[Tuple]:
        """זיהוי קווים אנכיים"""
        # יצירת kernel אנכי
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 30))
        
        # זיהוי קווים אנכיים
        vertical_lines_img = cv2.morphologyEx(image, cv2.MORPH_OPEN, vertical_kernel)
        
        # זיהוי קווים עם Hough Transform
        edges = cv2.Canny(vertical_lines_img, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80, minLineLength=100, maxLineGap=10)
        
        vertical_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # סינון קווים אנכיים
                angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
                if angle > 75:  # קווים כמעט אנכיים
                    vertical_lines.append((x1, y1, x2, y2))
        
        # מיון לפי X (משמאל לימין)
        vertical_lines.sort(key=lambda line: (line[0] + line[2]) / 2)
        
        return vertical_lines
    
    def _calculate_table_angle(self, horizontal_lines: List[Tuple]) -> float:
        """חישוב זווית הטיה של הטבלה"""
        if not horizontal_lines:
            return 0.0
            
        angles = []
        for x1, y1, x2, y2 in horizontal_lines:
            if x2 != x1:  # מניעת חלוקה באפס
                angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
                angles.append(angle)
        
        if angles:
            return np.median(angles)
        return 0.0
    
    def _find_table_bounds(self, horizontal_lines: List[Tuple], vertical_lines: List[Tuple]) -> Tuple[int, int, int, int]:
        """מציאת גבולות הטבלה"""
        if not horizontal_lines or not vertical_lines:
            return (0, 0, 0, 0)
            
        # מציאת גבולות
        all_x = [x for line in horizontal_lines + vertical_lines for x in [line[0], line[2]]]
        all_y = [y for line in horizontal_lines + vertical_lines for y in [line[1], line[3]]]
        
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        
        return (x_min, y_min, x_max, y_max)
    
    def _extract_table_cells(self, image: np.ndarray, table_structure: Dict) -> List[List[Dict]]:
        """חילוץ תאי הטבלה"""
        cells = []
        horizontal_lines = table_structure["horizontal_lines"]
        vertical_lines = table_structure["vertical_lines"]
        table_angle = table_structure["table_angle"]
        
        # הגבלת מספר השורות והעמודות למניעת לולאות אינסופיות
        max_rows = min(len(horizontal_lines) - 1, 20)  # מקסימום 20 שורות
        max_cols = min(len(vertical_lines) - 1, 10)    # מקסימום 10 עמודות
        
        if self.debug_mode:
            print(f"מחלץ טבלה: {max_rows} שורות, {max_cols} עמודות")
        
        # יצירת רשת תאים
        for i in range(max_rows):
            row_cells = []
            
            if self.debug_mode:
                print(f"מעבד שורה {i+1}/{max_rows}")
            
            # קבלת Y של השורה הנוכחית והבאה
            y_top = min(horizontal_lines[i][1], horizontal_lines[i][3])
            y_bottom = max(horizontal_lines[i+1][1], horizontal_lines[i+1][3])
            
            for j in range(max_cols):
                # חישוב X עם פיצוי זווית
                x_left = self._compensate_x_for_angle(vertical_lines[j], y_top, table_angle)
                x_right = self._compensate_x_for_angle(vertical_lines[j+1], y_top, table_angle)
                
                # חילוץ תא (עם timeout פנימי)
                cell_roi = self._extract_cell_roi(image, x_left, y_top, x_right, y_bottom)
                
                # OCR מהיר יותר - רק אם התא גדול מספיק
                if cell_roi.size > 100:  # לפחות 100 פיקסלים
                    cell_text = self._extract_text_from_roi(cell_roi)
                else:
                    cell_text = ""  # דלג על תאים קטנים
                
                cell_data = {
                    "row": i,
                    "col": j, 
                    "bounds": (x_left, y_top, x_right, y_bottom),
                    "text": cell_text.strip(),
                    "confidence": self._calculate_text_confidence(cell_text)
                }
                
                row_cells.append(cell_data)
            
            cells.append(row_cells)
        
        return cells
    
    def _compensate_x_for_angle(self, vertical_line: Tuple, target_y: int, table_angle: float) -> int:
        """פיצוי קואורדינטת X לפי זווית הטבלה"""
        x1, y1, x2, y2 = vertical_line
        
        if y2 == y1:  # קו אופקי - אין פיצוי
            return int((x1 + x2) / 2)
            
        # חישוב X בנקודת Y הרצויה
        line_slope = (x2 - x1) / (y2 - y1)
        x_at_target_y = x1 + line_slope * (target_y - y1)
        
        return int(x_at_target_y)
    
    def _extract_cell_roi(self, image: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        """חילוץ ROI של תא בודד"""
        # וידוא שהקואורדינטות בגבולות התמונה
        h, w = image.shape[:2]
        x1, y1 = max(0, min(x1, w-1)), max(0, min(y1, h-1))
        x2, y2 = max(0, min(x2, w-1)), max(0, min(y2, h-1))
        
        # וידוא שהקואורדינטות הגיוניות
        if x2 <= x1 or y2 <= y1:
            return np.zeros((10, 10), dtype=np.uint8)
            
        roi = image[y1:y2, x1:x2]
        
        # שיפור ROI לOCR טוב יותר
        if roi.size > 0:
            roi = self._enhance_roi_for_ocr(roi)
            
        return roi
    
    def _enhance_roi_for_ocr(self, roi: np.ndarray) -> np.ndarray:
        """שיפור ROI לOCR טוב יותר"""
        if roi.size == 0:
            return roi
            
        # הגדלה
        scale_factor = 2
        roi = cv2.resize(roi, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
        
        # שיפור ניגודיות
        if len(roi.shape) == 3:
            roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        roi = clahe.apply(roi)
        
        # הפחתת רעש
        roi = cv2.medianBlur(roi, 3)
        
        return roi
    
    def _extract_text_from_roi(self, roi: np.ndarray) -> str:
        """חילוץ טקסט מROI"""
        if roi.size == 0:
            return ""
            
        try:
            # נסה עברית + אנגלית
            text = pytesseract.image_to_string(
                roi, 
                lang='heb+eng',
                config='--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            )
            
            if not text.strip():
                # נסה רק אנגלית
                text = pytesseract.image_to_string(
                    roi,
                    lang='eng', 
                    config='--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                )
                
            return text.strip()
            
        except Exception as e:
            logging.error(f"שגיאה בחילוץ טקסט מROI: {str(e)}")
            return ""
    
    def _calculate_text_confidence(self, text: str) -> float:
        """חישוב ביטחון בטקסט שחולץ"""
        if not text or not text.strip():
            return 0.0
            
        # הערכה פשוטה - ככל שיש יותר תווים אלפאנומריים, הביטחון גבוה יותר
        alphanumeric_count = sum(c.isalnum() for c in text)
        total_chars = len(text.strip())
        
        if total_chars == 0:
            return 0.0
            
        confidence = alphanumeric_count / total_chars
        return min(confidence, 1.0)
    
    def _extract_item_codes(self, cells: List[List[Dict]]) -> List[str]:
        """חילוץ מק"טים ספציפי מהתאים"""
        item_codes = []
        
        if not cells:
            return item_codes
            
        # נחפש עמודת מק"ט (בדרך כלל עמודה 1 או 2)
        item_code_col = self._find_item_code_column(cells)
        
        if item_code_col == -1:
            return item_codes
            
        # חילוץ מק"טים מהעמודה המזוהה
        for row in cells:
            if item_code_col < len(row):
                cell_text = row[item_code_col]["text"]
                if self._is_valid_item_code(cell_text):
                    item_codes.append(cell_text)
        
        return item_codes
    
    def _find_item_code_column(self, cells: List[List[Dict]]) -> int:
        """מציאת עמודת המק"ט"""
        if not cells or not cells[0]:
            return -1
            
        # בדוק עמודות 1-3 (הכי נפוצות למק"ט)
        for col in range(min(3, len(cells[0]))):
            valid_codes = 0
            total_cells = 0
            
            for row in cells:
                if col < len(row):
                    cell_text = row[col]["text"]
                    total_cells += 1
                    if self._is_valid_item_code(cell_text):
                        valid_codes += 1
            
            # אם לפחות 50% מהתאים נראים כמו מק"טים
            if total_cells > 0 and (valid_codes / total_cells) >= 0.5:
                return col
        
        return -1
    
    def _is_valid_item_code(self, text: str) -> bool:
        """בדיקה אם טקסט נראה כמו מק"ט"""
        if not text or len(text) < 3:
            return False
            
        # מק"ט טיפוסי: מכיל אותיות ומספרים, אורך 4-20 תווים
        if not any(c.isdigit() for c in text):
            return False
            
        if not any(c.isalpha() for c in text):
            return False
            
        # אורך הגיוני
        if len(text) < 4 or len(text) > 20:
            return False
            
        # רוב התווים אלפאנומריים
        alphanumeric_ratio = sum(c.isalnum() for c in text) / len(text)
        if alphanumeric_ratio < 0.8:
            return False
            
        return True


def extract_table_data_advanced(image: np.ndarray, progress_callback=None) -> Dict:
    """פונקציה נוחה לחילוץ טבלאות מתקדם"""
    extractor = TableExtractor()
    return extractor.extract_table_data(image, progress_callback)


def format_table_data_as_text(table_data: Dict) -> str:
    """המרת נתוני הטבלה לטקסט מובנה לClaude"""
    try:
        formatted_text = []
        formatted_text.append("=== נתוני טבלה מתקדמים ===")
        
        if table_data.get("item_codes"):
            formatted_text.append("\n--- מק\"טים שזוהו ---")
            for i, code in enumerate(table_data["item_codes"], 1):
                formatted_text.append(f"מק\"ט {i}: {code}")
        
        if table_data.get("cells"):
            formatted_text.append("\n--- תוכן תאי הטבלה ---")
            cells = table_data["cells"]
            
            for row_idx, row in enumerate(cells):
                formatted_text.append(f"\nשורה {row_idx + 1}:")
                for col_idx, cell in enumerate(row):
                    if cell["text"] and cell["text"].strip():
                        formatted_text.append(f"  עמודה {col_idx + 1}: {cell['text']}")
        
        # הוסף את הטקסט הרגיל כגיבוי
        formatted_text.append("\n=== טקסט רגיל (גיבוי) ===")
        
        return "\n".join(formatted_text)
        
    except Exception as e:
        return f"שגיאה בעיצוב נתוני טבלה: {str(e)}"