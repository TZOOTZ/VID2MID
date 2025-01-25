# core/motion_detector.py
import cv2
import numpy as np
import yaml
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MotionDetector:
    def __init__(self, config_path="config.yaml", progress_callback=None, show_preview=False):
        self.progress_callback = progress_callback
        self.show_preview = show_preview
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                self.config = yaml.safe_load(f) or {}
        except Exception as e:
            raise ValueError(f"Error cargando configuración: {str(e)}")

        # Configuración con valores por defecto
        self.roi = self.config.get("global", {}).get("roi", [0, 0, 1920, 1080])
        self.blur_size = self.config.get("global", {}).get("blur", 5)
        self.color_change_threshold = self.config.get("global", {}).get("color_change_threshold", 15)
        self.prev_hsv = None
        self.frame_size = None

        # Add validation for critical config values
        if not all(isinstance(x, int) for x in self.roi):
            raise ValueError("ROI must contain integer values")
        if len(self.roi) != 4:
            raise ValueError("ROI must contain exactly 4 values [x1, y1, x2, y2]")

    def analyze_video(self, video_path):
        """Analiza el video y devuelve datos para 3 pistas MIDI"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"No se pudo abrir el video: {video_path}")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            logger.info(f"Processing video: {fps:.2f} FPS, {total_frames} frames")
            
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._validate_roi(width, height)
            
            results = defaultdict(list)
            frame_count = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                if frame is None or frame.size == 0:
                    logger.warning(f"Frame {frame_count} empty/corrupt, skipping...")
                    frame_count += 1
                    continue

                try:
                    current_time = cap.get(cv2.CAP_PROP_POS_MSEC)
                    processed = self._preprocess_frame(frame, show_preview=self.show_preview)
                    if processed is None:
                        continue
                    
                    # 1. Background Analysis
                    bg_data = self._analyze_background(processed)
                    bg_data["time"] = current_time
                    results["background"].append(bg_data)
                    
                    # 2. Medium Motion Analysis
                    mid_data = self._analyze_mid_motion(processed)
                    mid_data["time"] = current_time
                    results["medium"].append(mid_data)
                    
                    # 3. Detail Detection
                    details_data = self._detect_details(processed)
                    for detail in details_data:
                        detail["time"] = current_time
                    results["details"].extend(details_data)
                    
                    self.prev_hsv = processed.copy()
                    if self.progress_callback:
                        self.progress_callback(frame_count, total_frames)
                    frame_count += 1

                except Exception as e:
                    logger.error(f"Error processing frame {frame_count}: {str(e)}")
                    continue

            cap.release()
            return dict(results)

        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            raise

    def _validate_roi(self, width, height):
        """Asegura que el ROI esté dentro de las dimensiones del video"""
        try:
            # Ensure ROI is within video dimensions
            valid_roi = [
                max(0, min(self.roi[0], width-1)),
                max(0, min(self.roi[1], height-1)),
                max(1, min(self.roi[2], width)),
                max(1, min(self.roi[3], height))
            ]
            
            # Ensure ROI has positive dimensions
            if valid_roi[2] <= valid_roi[0] or valid_roi[3] <= valid_roi[1]:
                logger.warning("Invalid ROI dimensions, using full frame")
                self.roi = [0, 0, width, height]
            else:
                self.roi = valid_roi
            
        except Exception as e:
            logger.error(f"Error validating ROI: {str(e)}")
            self.roi = [0, 0, width, height]

    def _preprocess_frame(self, frame, show_preview=False):
        """Preprocesamiento del frame para análisis"""
        try:
            if frame is None or frame.size == 0:
                return None
                
            # Process frame
            roi = frame[self.roi[1]:self.roi[3], self.roi[0]:self.roi[2]]
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            processed = cv2.GaussianBlur(hsv, (self.blur_size, self.blur_size), 0)
            
            if show_preview:
                # Draw analysis visualization
                preview = frame.copy()
                cv2.rectangle(preview, (self.roi[0], self.roi[1]), 
                             (self.roi[2], self.roi[3]), (0,255,0), 2)
                cv2.imshow('Analysis Preview', preview)
                cv2.waitKey(1)
            
            return processed
            
        except Exception as e:
            print(f"Error preprocesando frame: {str(e)}")
            return None

    def _analyze_background(self, current_hsv):
        """Analiza cambios globales en el fondo"""
        try:
            if self.prev_hsv is None:
                return {"hue_shift": 0.0, "value_shift": 0.0}
                
            # Diferencia en el canal de tono (Hue)
            hue_diff = cv2.absdiff(current_hsv[:,:,0], self.prev_hsv[:,:,0])
            hue_shift = np.mean(hue_diff) / 179.0  # Normalizado 0-1
            
            # Diferencia en luminosidad (Value)
            val_diff = cv2.absdiff(current_hsv[:,:,2], self.prev_hsv[:,:,2])
            value_shift = np.mean(val_diff) / 255.0
            
            return {
                "hue_shift": hue_shift,
                "value_shift": value_shift
            }
            
        except Exception as e:
            print(f"Error análisis fondo: {str(e)}")
            return {"hue_shift": 0.0, "value_shift": 0.0}

    def _analyze_mid_motion(self, current_hsv):
        """Analiza movimiento en áreas medianas"""
        try:
            if self.prev_hsv is None:
                return {"intensity": 0.0, "direction": 0.0, "time": 0.0}
                
            # Get zone configuration with fallback to full ROI
            zone_config = self.config.get("tracks", {}).get("medium", {}).get("zone", self.roi)
            x1, y1, x2, y2 = self._convert_to_roi_coordinates(zone_config)
            
            # Ensure we have valid dimensions
            if x2 <= x1 or y2 <= y1:
                logger.debug("Using minimum ROI size")
                x1, y1 = 0, 0
                x2, y2 = current_hsv.shape[1], current_hsv.shape[0]

            # Convert HSV to BGR safely
            try:
                prev_frame = cv2.cvtColor(self.prev_hsv[y1:y2, x1:x2], cv2.COLOR_HSV2BGR)
                curr_frame = cv2.cvtColor(current_hsv[y1:y2, x1:x2], cv2.COLOR_HSV2BGR)
            except cv2.error as e:
                logger.error(f"Color conversion error: {e}")
                return {"intensity": 0.0, "direction": 0.0, "time": 0.0}
            
            # Convert to grayscale for optical flow
            prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
            curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
            
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
            
            magnitude, angle = cv2.cartToPolar(flow[...,0], flow[...,1])
            return {
                "intensity": float(np.mean(magnitude)),
                "direction": float(np.degrees(np.mean(angle)) % 360),
                "time": 0.0  # Will be set by caller
            }
            
        except Exception as e:
            logger.error(f"Error in motion analysis: {str(e)}")
            return {"intensity": 0.0, "direction": 0.0, "time": 0.0}

    def _detect_details(self, current_hsv):
        """Detecta pequeñas explosiones de color"""
        try:
            # Máscara para colores saturados
            lower = np.array([0, 150, 200])
            upper = np.array([180, 255, 255])
            mask = cv2.inRange(current_hsv, lower, upper)
            
            # Operaciones morfológicas
            kernel = np.ones((3,3), np.uint8)
            cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
            
            # Detección de contornos
            contours, _ = cv2.findContours(
                cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            
            events = []
            min_area = self.config.get("tracks", {}).get("details", {}).get("min_area", 30)
            
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > min_area:
                    M = cv2.moments(cnt)
                    if M["m00"] == 0:
                        continue
                        
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    hue = current_hsv[cy, cx, 0]
                    
                    events.append({
                        "x": cx + self.roi[0],
                        "y": cy + self.roi[1],
                        "size": area,
                        "hue": hue
                    })
                    
            return events
            
        except Exception as e:
            print(f"Error detección detalles: {str(e)}")
            return []

    def _convert_to_roi_coordinates(self, zone):
        """Convierte coordenadas absolutas a relativas al ROI"""
        try:
            # Ensure zone is valid
            if not zone or len(zone) != 4:
                logger.warning("Invalid zone configuration, using default ROI")
                return [0, 0, self.roi[2]-self.roi[0], self.roi[3]-self.roi[1]]
            
            # Convert to relative coordinates
            rel_coords = [
                max(0, zone[0] - self.roi[0]),
                max(0, zone[1] - self.roi[1]),
                min(zone[2] - self.roi[0], self.roi[2]-self.roi[0]),
                min(zone[3] - self.roi[1], self.roi[3]-self.roi[1])
            ]
            
            # Validate coordinates
            if rel_coords[2] <= rel_coords[0] or rel_coords[3] <= rel_coords[1]:
                logger.warning("Invalid relative coordinates, using full ROI")
                return [0, 0, self.roi[2]-self.roi[0], self.roi[3]-self.roi[1]]
            
            return rel_coords
            
        except Exception as e:
            logger.error(f"Error converting coordinates: {str(e)}")
            return [0, 0, self.roi[2]-self.roi[0], self.roi[3]-self.roi[1]]