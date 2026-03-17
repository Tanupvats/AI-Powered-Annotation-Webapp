import React, { useEffect, useRef, useState } from "react";
import { Streamlit, withStreamlitConnection } from "streamlit-component-lib";
import { fabric } from "fabric";

const CVCanvas = ({ args }) => {
  const canvasEl = useRef(null);
  const [mode, setMode] = useState("draw"); 
  
  const fabricCanvasRef = useRef(null);
  const imgScaleRef = useRef(1);
  const polyPointsRef = useRef([]);
  const drawingObjectsRef = useRef([]); 
  const redrawRef = useRef(null);
  
  const modeRef = useRef(mode);
  
  const { 
    imageUrl, 
    toolMode, 
    brushSize = 20, 
    solidColor = "rgb(0, 255, 0)", 
    transColor = "rgba(0, 255, 0, 0.3)",
    resetCounter = 0 
  } = args || {};

  const brushSizeRef = useRef(brushSize);
  const rectRef = useRef(null);
  const origXRef = useRef(0);
  const origYRef = useRef(0);

  
  const handleUndo = () => {
    if (toolMode === "polygon") {
      if (polyPointsRef.current.length > 0 && redrawRef.current) {
        polyPointsRef.current.pop(); 
        redrawRef.current(); 
      }
    } else if (toolMode === "brush") {
      const canvas = fabricCanvasRef.current;
      if (canvas) {
        
        const objects = canvas.getObjects();
        
        if (objects.length > 0) {
          canvas.remove(objects[objects.length - 1]);
          canvas.renderAll();
        }
      }
    }
  };

  useEffect(() => {
    Streamlit.setFrameHeight(600);
  }, []);

  useEffect(() => {
    modeRef.current = mode;
    if (fabricCanvasRef.current) {
      fabricCanvasRef.current.isDrawingMode = (toolMode === "brush" && mode === "draw");
    }
  }, [mode, toolMode]);

  useEffect(() => {
    brushSizeRef.current = brushSize;
    if (fabricCanvasRef.current && fabricCanvasRef.current.freeDrawingBrush) {
      fabricCanvasRef.current.freeDrawingBrush.width = brushSize;
    }
  }, [brushSize]);

  useEffect(() => {
    if (fabricCanvasRef.current && resetCounter > 0) {
      const canvas = fabricCanvasRef.current;
      const objects = canvas.getObjects();
      
      objects.forEach(obj => {
         canvas.remove(obj);
      });
      
      polyPointsRef.current = [];
      drawingObjectsRef.current = [];
      rectRef.current = null;
      
      Streamlit.setComponentValue({}); 
      canvas.renderAll();
    }
  }, [resetCounter]);


  useEffect(() => {
    if (!imageUrl) return;

    const initCanvas = new fabric.Canvas(canvasEl.current, {
      width: 600,
      height: 500,
      isDrawingMode: toolMode === "brush" && modeRef.current === "draw",
      selection: false,
      enableRetinaScaling: false, 
      fireRightClick: true,  
      stopContextMenu: true, 
    });
    
    fabricCanvasRef.current = initCanvas;
    polyPointsRef.current = []; 

    if (toolMode === "brush") {
      initCanvas.freeDrawingBrush.color = transColor;
      initCanvas.freeDrawingBrush.width = brushSizeRef.current;
    }

    fabric.Image.fromURL(imageUrl, (img) => {
      if (!img) return;
      const scale = Math.min(initCanvas.width / img.width, initCanvas.height / img.height);
      imgScaleRef.current = scale;
      
      img.set({
        originX: "left", originY: "top", left: 0, top: 0,
        scaleX: scale, scaleY: scale, selectable: false,
        objectCaching: false 
      });
      initCanvas.setBackgroundImage(img, initCanvas.renderAll.bind(initCanvas));
      Streamlit.setFrameHeight(initCanvas.height + 100);
    });

    initCanvas.on('path:created', function(opt) {
      if (toolMode === "brush") {
        opt.path.set({ stroke: solidColor, opacity: 0.4 });
        initCanvas.renderAll();
      }
    });

    redrawRef.current = () => {
      const canvas = fabricCanvasRef.current;
      if (!canvas) return;

      drawingObjectsRef.current.forEach(obj => canvas.remove(obj));
      drawingObjectsRef.current = [];

      const points = polyPointsRef.current;
      if (points.length === 0) {
        canvas.renderAll();
        return;
      }

      const scale = imgScaleRef.current;
      const scaledPoints = points.map(p => ({ x: p.x * scale, y: p.y * scale }));

      if (points.length >= 3) {
        const poly = new fabric.Polygon(scaledPoints, {
          fill: transColor,        
          stroke: solidColor,      
          strokeWidth: 2 / canvas.getZoom(), 
          selectable: false, evented: false, objectCaching: false 
        });
        canvas.add(poly);
        drawingObjectsRef.current.push(poly);
      } 
      else if (points.length === 2) {
        const line = new fabric.Line([scaledPoints[0].x, scaledPoints[0].y, scaledPoints[1].x, scaledPoints[1].y], {
          stroke: solidColor, strokeWidth: 2 / canvas.getZoom(), selectable: false, evented: false
        });
        canvas.add(line);
        drawingObjectsRef.current.push(line);
      }

      scaledPoints.forEach(p => {
        const circle = new fabric.Circle({
          radius: 4 / canvas.getZoom(), fill: solidColor, left: p.x, top: p.y, originX: 'center', originY: 'center',
          selectable: false, evented: false
        });
        canvas.add(circle);
        drawingObjectsRef.current.push(circle);
      });

      canvas.renderAll();
    };

    initCanvas.on('mouse:wheel', function(opt) {
      var delta = opt.e.deltaY;
      var zoom = initCanvas.getZoom();
      zoom *= 0.999 ** delta;
      if (zoom > 20) zoom = 20;
      if (zoom < 0.5) zoom = 0.5;
      initCanvas.zoomToPoint({ x: opt.e.offsetX, y: opt.e.offsetY }, zoom);

      if (initCanvas.freeDrawingBrush) {
        initCanvas.freeDrawingBrush.width = brushSizeRef.current;
      }
      if (toolMode === "polygon") { redrawRef.current(); }

      opt.e.preventDefault();
      opt.e.stopPropagation();
    });

    let isDragging = false;
    let lastPosX, lastPosY;

    initCanvas.on('mouse:down', function(opt) {
      const evt = opt.e;
      const isRightClick = opt.button === 3;
      const isLeftClick = opt.button === 1 || opt.button === undefined;

      if (modeRef.current === "pan") {
        if (isLeftClick) {
          isDragging = true; lastPosX = evt.clientX; lastPosY = evt.clientY;
        }
        return;
      }

      if (modeRef.current === "draw") {
        if (isRightClick) {
          if (toolMode === "polygon" && polyPointsRef.current.length > 2) {
            Streamlit.setComponentValue({ polygon: polyPointsRef.current });
          } 
          else if (toolMode === "brush") {
            const bg = initCanvas.backgroundImage;
            const exportW = Math.round(bg.getScaledWidth());
            const exportH = Math.round(bg.getScaledHeight());
            initCanvas.backgroundImage = null;
            const vpt = initCanvas.viewportTransform.slice(0);
            initCanvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
            const dataUrl = initCanvas.toDataURL({ 
              format: 'png', multiplier: 1 / imgScaleRef.current, left: 0, top: 0, width: exportW, height: exportH
            });
            initCanvas.setViewportTransform(vpt);
            initCanvas.backgroundImage = bg;
            initCanvas.renderAll();
            Streamlit.setComponentValue({ brushMask: dataUrl });
          }
          else if (toolMode === "rect") {
            const oldRects = initCanvas.getObjects('rect');
            if (oldRects.length > 0) {
              const lastRect = oldRects[oldRects.length - 1];
              const scale = imgScaleRef.current;
              const bbox = {
                x: lastRect.left / scale, y: lastRect.top / scale,
                w: lastRect.width / scale, h: lastRect.height / scale
              };
              Streamlit.setComponentValue({ rect: bbox });
            }
          }
          return; 
        }

        if (isLeftClick) {
          const pointer = initCanvas.getPointer(opt.e);
          const scale = imgScaleRef.current;
          const actualX = pointer.x / scale;
          const actualY = pointer.y / scale;

          if (toolMode === "point") {
            const oldPoints = initCanvas.getObjects('circle').filter(obj => obj.fill === 'red');
            oldPoints.forEach(obj => initCanvas.remove(obj));
            initCanvas.add(new fabric.Circle({ 
              radius: 6 / initCanvas.getZoom(), fill: 'red', left: pointer.x, top: pointer.y, originX: 'center', originY: 'center', selectable: false 
            }));
            Streamlit.setComponentValue({ point: { x: actualX, y: actualY } });
          } 
          else if (toolMode === "polygon") {
            polyPointsRef.current.push({ x: actualX, y: actualY });
            redrawRef.current(); 
          }
          else if (toolMode === "rect") {
            const oldRects = initCanvas.getObjects('rect');
            oldRects.forEach(obj => initCanvas.remove(obj));

            origXRef.current = pointer.x;
            origYRef.current = pointer.y;

            const rect = new fabric.Rect({
              left: pointer.x, top: pointer.y, originX: 'left', originY: 'top',
              width: 0, height: 0, 
              fill: transColor,     
              stroke: solidColor,   
              strokeWidth: 2 / initCanvas.getZoom(), selectable: false, evented: false
            });
            initCanvas.add(rect);
            rectRef.current = rect;
          }
        }
      }
    });

    initCanvas.on('mouse:move', function(opt) {
      if (isDragging && modeRef.current === "pan") {
        const e = opt.e;
        const vpt = initCanvas.viewportTransform;
        vpt[4] += e.clientX - lastPosX;
        vpt[5] += e.clientY - lastPosY;
        initCanvas.requestRenderAll();
        lastPosX = e.clientX;
        lastPosY = e.clientY;
      }

      if (modeRef.current === "draw" && toolMode === "rect" && rectRef.current) {
        const pointer = initCanvas.getPointer(opt.e);
        const rect = rectRef.current;
        if(origXRef.current > pointer.x){ rect.set({ left: pointer.x }); }
        if(origYRef.current > pointer.y){ rect.set({ top: pointer.y }); }
        rect.set({ width: Math.abs(origXRef.current - pointer.x) });
        rect.set({ height: Math.abs(origYRef.current - pointer.y) });
        initCanvas.requestRenderAll();
      }
    });

    initCanvas.on('mouse:up', function() { 
      isDragging = false; 
      if (toolMode === "rect" && rectRef.current) {
        rectRef.current = null;
      }
    });

    return () => { 
      initCanvas.dispose(); 
      fabricCanvasRef.current = null;
    };
    
  }, [toolMode, imageUrl, solidColor, transColor]); 

  return (
    <div style={{ fontFamily: "sans-serif" }}>
      <div style={{ marginBottom: "10px", padding: "10px", background: "#f0f2f6", borderRadius: "5px", display: "flex", alignItems: "center", gap: "15px", flexWrap: "wrap" }}>
        <strong>Mode: </strong>
        <label style={{ cursor: "pointer" }}>
          <input type="radio" checked={mode === "draw"} onChange={() => setMode("draw")} /> ✏️ Draw/Select
        </label>
        <label style={{ cursor: "pointer" }}>
          <input type="radio" checked={mode === "pan"} onChange={() => setMode("pan")} /> ✋ Pan Image
        </label>

        {/* ---  Undo Button for both Brush and Polygon tools! --- */}
        {(toolMode === "polygon" || toolMode === "brush") && mode === "draw" && (
          <button 
            onClick={handleUndo} 
            style={{ 
              marginLeft: "15px", padding: "4px 12px", background: "#ff4b4b", color: "white", 
              border: "none", borderRadius: "4px", cursor: "pointer", fontWeight: "bold"
            }}>
            ↩ Undo Last {toolMode === "brush" ? "Stroke" : "Point"}
          </button>
        )}

        <span style={{ fontSize: "14px", color: "#666", marginLeft: "auto" }}>
          <em>(Right-Click to send shape | Scroll to zoom)</em>
        </span>
      </div>
      <canvas ref={canvasEl} style={{ border: "1px solid #ccc", borderRadius: "5px" }} />
    </div>
  );
};

export default withStreamlitConnection(CVCanvas);