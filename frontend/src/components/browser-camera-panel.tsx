import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, CircleAlert, CircleCheck, Play, Square } from 'lucide-react'
import type { Camera as CameraInfo } from '../data'
import { api } from '@/services/api'
import './browser-camera-panel.css'

interface VideoDevice {
  deviceId: string
  label: string
}

interface CameraDetection {
  class_name: string
  confidence: number
  bbox: [number, number, number, number]
}

interface CameraFrameResult {
  width: number
  height: number
  detections: CameraDetection[]
  violations: { description: string; bbox: [number, number, number, number] }[]
  new_incidents: string[]
  metrics: { backend: string; inference_ms: number; fps: number }
}

export function BrowserCameraPanel({ cameras, siteId }: { cameras: CameraInfo[]; siteId: string }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const overlayRef = useRef<HTMLCanvasElement>(null)
  const captureRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const sendingRef = useRef(false)
  const cameraIdRef = useRef('')
  const [devices, setDevices] = useState<VideoDevice[]>([])
  const [deviceId, setDeviceId] = useState('')
  const [zoneCameraId, setZoneCameraId] = useState(cameras[0]?.id ?? '')
  const [cameraId, setCameraId] = useState('')
  const [running, setRunning] = useState(false)
  const [status, setStatus] = useState('Камера не подключена')
  const [error, setError] = useState('')
  const [latestIncident, setLatestIncident] = useState('')
  const [metrics, setMetrics] = useState<CameraFrameResult['metrics'] | null>(null)
  cameraIdRef.current = cameraId

  useEffect(() => {
    if (!cameras.some((camera) => camera.id === zoneCameraId)) {
      if (cameraId) {
        void api.setBrowserCameraOnline(cameraId, false).catch((reason: unknown) => {
          setError(reason instanceof Error ? reason.message : 'Не удалось обновить статус камеры.')
        })
      }
      setCameraId('')
      setZoneCameraId(cameras[0]?.id ?? '')
    }
  }, [cameraId, zoneCameraId, cameras])

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    const activeCameraId = cameraIdRef.current
    if (activeCameraId) {
      void api.setBrowserCameraOnline(activeCameraId, false).catch((reason: unknown) => {
        console.error('Failed to mark browser camera offline', reason)
      })
    }
  }, [])

  const clearOverlay = useCallback(() => {
    const canvas = overlayRef.current
    if (!canvas) return
    const context = canvas.getContext('2d')
    context?.clearRect(0, 0, canvas.width, canvas.height)
  }, [])

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setRunning(false)
    setStatus('Камера не подключена')
    setMetrics(null)
    clearOverlay()
    if (cameraId) {
      void api.setBrowserCameraOnline(cameraId, false).catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Не удалось обновить статус камеры.')
      })
    }
  }, [cameraId, clearOverlay])

  const startCamera = async (selectedDeviceId = deviceId) => {
    setError('')
    setLatestIncident('')
    const zoneCamera = cameras.find((camera) => camera.id === zoneCameraId)
    if (!zoneCamera) {
      setError('На этой площадке нет зарегистрированной камеры, чтобы выбрать зону.')
      return
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Браузер не поддерживает доступ к камере. Откройте сайт через HTTPS или localhost.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: selectedDeviceId ? { deviceId: { exact: selectedDeviceId } } : { facingMode: 'environment' },
      })
      streamRef.current = stream
      const available = await navigator.mediaDevices.enumerateDevices()
      const videoDevices = available
        .filter((device) => device.kind === 'videoinput')
        .map((device, index) => ({
          deviceId: device.deviceId,
          label: device.label || `Камера ${index + 1}`,
        }))
      setDevices(videoDevices)
      const activeDevice = stream.getVideoTracks()[0]?.getSettings().deviceId
      if (activeDevice) setDeviceId(activeDevice)
      const trackName = stream.getVideoTracks()[0]?.label || 'Браузерная камера'
      const registration = cameraId
        ? { id: cameraId }
        : await api.registerBrowserCamera(siteId, trackName, zoneCamera.zone, zoneCamera.workshop)
      setCameraId(registration.id)
      await api.setBrowserCameraOnline(registration.id, true)
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setRunning(true)
      setStatus(`Камера ${registration.id} подключена · анализ запускается`)
    } catch (reason) {
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
      const message = reason instanceof Error ? reason.message : 'Не удалось получить доступ к камере.'
      setError(message)
      setStatus('Не удалось подключить камеру')
    }
  }

  useEffect(() => {
    if (!running) return
    let cancelled = false
    const timer = window.setInterval(async () => {
      const video = videoRef.current
      const capture = captureRef.current
      if (
        !video || !capture || video.videoWidth === 0 || video.videoHeight === 0
        || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || sendingRef.current
      ) return
      sendingRef.current = true
      try {
        const scale = Math.min(1, 960 / video.videoWidth, 540 / video.videoHeight)
        capture.width = Math.max(1, Math.round(video.videoWidth * scale))
        capture.height = Math.max(1, Math.round(video.videoHeight * scale))
        const context = capture.getContext('2d')
        if (!context) throw new Error('Не удалось подготовить кадр камеры.')
        context.drawImage(video, 0, 0, capture.width, capture.height)
        const blob = await new Promise<Blob | null>((resolve) => capture.toBlob(resolve, 'image/jpeg', 0.75))
        if (!blob) throw new Error('Не удалось подготовить JPEG-кадр.')
        const result = await api.processBrowserCameraFrame(cameraId, blob)
        if (cancelled) return
        setStatus('Идёт анализ кадров')
        setMetrics(result.metrics)
        if (result.new_incidents.length) setLatestIncident(result.new_incidents[0])
        const overlay = overlayRef.current
        const overlayContext = overlay?.getContext('2d')
        if (!overlay || !overlayContext) return
        overlay.width = video.videoWidth
        overlay.height = video.videoHeight
        overlayContext.clearRect(0, 0, overlay.width, overlay.height)
        const scaleX = overlay.width / result.width
        const scaleY = overlay.height / result.height
        const violations = result.violations
        for (const detection of result.detections) {
          const [x1, y1, x2, y2] = detection.bbox
          const isViolation = detection.class_name === 'no_helmet' || violations.some((item) => {
            const [vx1, vy1, vx2, vy2] = item.bbox
            return x1 < vx2 && x2 > vx1 && y1 < vy2 && y2 > vy1
          })
          overlayContext.strokeStyle = isViolation ? '#ef4444' : '#22c55e'
          overlayContext.lineWidth = Math.max(2, overlay.width / 500)
          overlayContext.strokeRect(x1 * scaleX, y1 * scaleY, (x2 - x1) * scaleX, (y2 - y1) * scaleY)
          overlayContext.font = `${Math.max(14, overlay.width / 55)}px sans-serif`
          overlayContext.fillStyle = isViolation ? '#ef4444' : '#22c55e'
          overlayContext.fillText(
            `${detection.class_name} ${Math.round(detection.confidence * 100)}%`,
            x1 * scaleX,
            Math.max(20, y1 * scaleY - 6),
          )
        }
      } catch (reason) {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : 'Ошибка обработки кадра.')
          setStatus('Анализ остановлен из-за ошибки')
          stopCamera()
        }
      } finally {
        sendingRef.current = false
      }
    }, 500)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [cameraId, running, stopCamera])

  return (
    <section className="browser-camera-panel">
      <div className="browser-camera-heading">
        <div>
          <h2><Camera size={18} /> Проверить камеру прямо из браузера</h2>
          <p>Подключите веб-камеру или USB-камеру, которую видит система, и проверьте детекцию каски.</p>
        </div>
        <span className={`browser-camera-status ${running ? 'is-running' : ''}`}>
          <i /> {status}
        </span>
      </div>
      <div className="browser-camera-controls">
        <label>
          Камера устройства
          <select
            aria-label="Камера устройства"
            value={deviceId}
            disabled={running}
            onChange={(event) => setDeviceId(event.target.value)}
          >
            <option value="">Камера по умолчанию</option>
            {devices.map((device) => <option key={device.deviceId} value={device.deviceId}>{device.label}</option>)}
          </select>
        </label>
        <label>
          Зона камеры
          <select
            aria-label="Зона камеры"
            value={zoneCameraId}
            disabled={running}
            onChange={(event) => {
              if (cameraId) {
                void api.setBrowserCameraOnline(cameraId, false).catch((reason: unknown) => {
                  setError(reason instanceof Error ? reason.message : 'Не удалось обновить статус камеры.')
                })
              }
              setCameraId('')
              setZoneCameraId(event.target.value)
            }}
          >
            {cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.id} · {camera.name}</option>)}
          </select>
        </label>
        {running ? (
          <button type="button" className="browser-camera-action stop" onClick={stopCamera}>
            <Square size={15} /> Остановить
          </button>
        ) : (
          <button type="button" className="browser-camera-action" onClick={() => void startCamera()}>
            <Play size={15} /> Подключить
          </button>
        )}
      </div>
      <div className="browser-camera-preview">
        <video ref={videoRef} muted playsInline />
        <canvas ref={overlayRef} className="browser-camera-overlay" />
        <canvas ref={captureRef} className="browser-camera-capture" />
        {!running && <div className="browser-camera-empty"><Camera size={24} />Предпросмотр появится после подключения</div>}
      </div>
      <div className="browser-camera-footer">
        <span><CircleCheck size={15} /> Будет зарегистрирована отдельная камера, чтобы не смешивать кадры с RTSP-потоком. Подтверждённый инцидент поступит в журнал и подключённые каналы.</span>
        {metrics && <span>{metrics.backend} · {metrics.inference_ms.toFixed(0)} мс · {metrics.fps.toFixed(1)} FPS</span>}
      </div>
      {error && <div className="browser-camera-message error"><CircleAlert size={16} />{error}</div>}
      {latestIncident && <div className="browser-camera-message alert"><CircleAlert size={16} />{latestIncident} · инцидент отправлен в журнал и подключённые уведомления.</div>}
      <p className="browser-camera-note">
        Доступ к камере требует разрешения браузера и HTTPS либо localhost. Телефон Xiaomi через USB обычно передаёт только питание; он появится здесь, только если ОС распознаёт его как видеоустройство.
      </p>
    </section>
  )
}
