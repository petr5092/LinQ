export type Severity = 'critical' | 'warning' | 'info'
export type EventStatus = 'new' | 'working' | 'resolved' | 'dismissed'
export type SiteId = 'north'
export type SafetyEvent = {
  id: string
  site: SiteId
  title: string
  zone: string
  camera: string
  time: string
  severity: Severity
  type: 'person' | 'environment' | 'access'
  description: string
  action: string
  image: string
  video?: string
  employee?: { name: string; role: string; number: string; access: string }
  contact: { name: string; role: string; radio: string; phone: string }
  status: EventStatus
  box: [number, number, number, number]
  confidence?: number
}
export type Camera = {
  id: string
  name: string
  zone: string
  workshop: string
  site: SiteId
  image: string
  video?: string
  event?: string
  online: boolean
  cameraType?: 'visible' | 'thermal'
}
export type Workshop = { name: string; zones: string[] }
export type Site = { id: SiteId; name: string; subtitle: string; workshops: Workshop[] }
export type Account = { id: string; name: string; role: string; note: string; initials: string }

export const sites: Site[] = [
  {
    id: 'north',
    name: 'Завод «Северный»',
    subtitle: 'Основная площадка',
    workshops: [
      { name: 'Корпус А', zones: ['Цех № 1'] },
    ],
  },
]

export const accounts: Account[] = [
  { id: 'video-operator', name: 'Александр Козлов', role: 'Оператор видеонаблюдения', note: 'Центр мониторинга · смена 08:00–20:00', initials: 'АК' },
  { id: 'shift-leader', name: 'Алексей Морозов', role: 'Руководитель смены', note: 'Корпус А · смена 08:00–20:00', initials: 'АМ' },
  { id: 'enterprise-leader', name: 'Ирина Соколова', role: 'Руководитель предприятия', note: 'Администрация · Завод «Северный»', initials: 'ИС' },
  { id: 'safety-specialist', name: 'Ольга Белова', role: 'Специалист по охране труда', note: 'Служба охраны труда · Завод «Северный»', initials: 'ОБ' },
  { id: 'employee', name: 'Иван Петров', role: 'Работник предприятия', note: 'Цех № 1 · оператор станка', initials: 'ИП' },
  { id: 'safety-inspector', name: 'Сергей Волков', role: 'Инспектор по охране труда', note: 'Внутренний контроль · Завод «Северный»', initials: 'СВ' },
  { id: 'system-admin', name: 'Наталья Орлова', role: 'Системный администратор', note: 'ИТ-служба · управление системой', initials: 'НО' },
]

export const zoneNames = sites.flatMap((site) => site.workshops.flatMap((workshop) => workshop.zones))
export const zoneWorkshop: Record<string, string> = Object.fromEntries(
  sites.flatMap((site) => site.workshops.flatMap((workshop) => workshop.zones.map((zone) => [zone, workshop.name])))
)

const master = { name: 'Алексей Морозов', role: 'Мастер смены', radio: 'Канал 3 · Мастер-01', phone: '+7 (495) 555-01-20, доб. 203' }
const security = { name: 'Сергей Волков', role: 'Начальник охраны', radio: 'Канал 1 · Пост-01', phone: '+7 (495) 555-01-20, доб. 101' }
const warehouse = { name: 'Елена Кузнецова', role: 'Начальник склада', radio: 'Канал 4 · Склад-01', phone: '+7 (495) 555-01-20, доб. 304' }

export const initialEvents: SafetyEvent[] = [
  {
    id: 'TK-1048',
    site: 'north',
    title: 'Сотрудник без каски',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:32:08',
    severity: 'critical',
    type: 'person',
    description: 'Сотрудник находится в зоне работы оборудования без защитной каски более 15 секунд.',
    action: 'Свяжитесь с мастером смены. Остановите работы до устранения нарушения.',
    image: 'construction',
    video: '/videos/construction_safety.mp4',
    employee: { name: 'Иван Петров', role: 'Оператор станка · Цех № 1', number: '00482', access: 'Доступ разрешён · СКУД в 14:12' },
    contact: master,
    status: 'new',
    box: [63, 43, 9, 32],
  },
  {
    id: 'TK-1047',
    site: 'north',
    title: 'Попытка несанкционированного прохода',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:31:42',
    severity: 'critical',
    type: 'access',
    description:
      'СКУД отклонила проход: срок допуска к работам истёк 22.10.2026. Турникет заблокирован, сотрудник не допущен на территорию.',
    action: 'Передайте информацию охране. Для восстановления доступа сотруднику необходимо продлить допуск у специалиста по охране труда.',
    image: 'gate',
    employee: { name: 'Дмитрий Соколов', role: 'Подрядчик · ООО «Монтаж»', number: 'П-0136', access: 'В проходе отказано · Допуск истёк' },
    contact: security,
    status: 'new',
    box: [48, 24, 13, 47],
  },
  {
    id: 'TK-1046',
    site: 'north',
    title: 'Ящик в проходе',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:30:16',
    severity: 'info',
    type: 'environment',
    description: 'Посторонний ящик перекрывает пешеходный проход между стеллажами Б-3 и Б-4. Объект неподвижен 3 минуты.',
    action: 'Свяжитесь с начальником склада и организуйте освобождение прохода.',
    image: 'warehouse',
    contact: warehouse,
    status: 'new',
    box: [66, 43, 12, 17],
  },
  {
    id: 'TK-1045',
    site: 'north',
    title: 'Жидкость на полу',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:28:51',
    severity: 'info',
    type: 'environment',
    description: 'Обнаружена лужа рядом со станком № 4. Возможная утечка охлаждающей жидкости, риск скольжения.',
    action: 'Оградите участок и вызовите дежурного механика для проверки оборудования.',
    image: 'workshop',
    contact: {
      ...master,
      name: 'Павел Орлов',
      role: 'Дежурный механик',
      radio: 'Канал 3 · Механик-02',
      phone: '+7 (495) 555-01-20, доб. 215',
    },
    status: 'working',
    box: [38, 68, 31, 19],
  },
  {
    id: 'TK-1044',
    site: 'north',
    title: 'Перелезание через ограждение',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:27:03',
    severity: 'critical',
    type: 'access',
    description: 'Камера зафиксировала человека, пересекающего северное ограждение вне оборудованного прохода. Личность не установлена.',
    action: 'Незамедлительно направьте патруль на северный периметр, сектор 4.',
    image: 'perimeter',
    contact: security,
    status: 'new',
    box: [46, 40, 9, 31],
  },
  {
    id: 'TK-1043',
    site: 'north',
    title: 'Опасное сближение с погрузчиком',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:25:39',
    severity: 'critical',
    type: 'person',
    description: 'Расстояние от пешехода до движущегося погрузчика меньше 1,5 метра. Зафиксировано пересечение транспортного маршрута.',
    action: 'Предупредите водителя и остановите движение на участке.',
    image: 'warehouse',
    employee: { name: 'Андрей Смирнов', role: 'Комплектовщик', number: '00317', access: 'Доступ разрешён · СКУД в 13:58' },
    contact: warehouse,
    status: 'working',
    box: [47, 36, 15, 39],
  },
  {
    id: 'TK-1042',
    site: 'north',
    title: 'Нет страховочной привязи',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:23:18',
    severity: 'critical',
    type: 'person',
    description: 'Сотрудник работает на площадке выше 1,8 метра без закреплённой страховочной привязи.',
    action: 'Приостановите высотные работы и свяжитесь с ответственным руководителем.',
    image: 'workshop',
    contact: master,
    status: 'new',
    box: [65, 25, 13, 40],
  },
  {
    id: 'TK-1041',
    site: 'north',
    title: 'Проход без респиратора отклонён',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:21:44',
    severity: 'warning',
    type: 'access',
    description: 'Вход в окрасочный цех заблокирован: отсутствует обязательный респиратор. Допуск к работам действителен.',
    action: 'Выдать респиратор и повторить проверку СИЗ перед проходом.',
    image: 'gate',
    employee: {
      name: 'Михаил Лебедев',
      role: 'Маляр · Окрасочный участок',
      number: '00561',
      access: 'В проходе отказано · Нет респиратора',
    },
    contact: master,
    status: 'new',
    box: [48, 24, 13, 47],
  },
  {
    id: 'TK-1040',
    site: 'north',
    title: 'Курение у горючих материалов',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:19:05',
    severity: 'warning',
    type: 'person',
    description: 'Зафиксировано курение рядом с участком хранения лакокрасочных материалов.',
    action: 'Немедленно прекратите нарушение и уведомите начальника склада.',
    image: 'warehouse',
    contact: warehouse,
    status: 'new',
    box: [35, 40, 12, 37],
  },
  {
    id: 'TK-1039',
    site: 'north',
    title: 'Телефон во время работы',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:16:32',
    severity: 'warning',
    type: 'person',
    description: 'Сотрудник использует мобильный телефон рядом с работающим станком.',
    action: 'Предупредите сотрудника через мастера смены.',
    image: 'workshop',
    contact: master,
    status: 'new',
    box: [63, 43, 9, 32],
  },
  {
    id: 'TK-1038',
    site: 'north',
    title: 'Проход под подвешенным грузом',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:14:11',
    severity: 'warning',
    type: 'person',
    description: 'Человек находится в опасной зоне перемещения груза мостовым краном.',
    action: 'Остановите перемещение груза и освободите опасную зону.',
    image: 'workshop',
    contact: master,
    status: 'new',
    box: [45, 35, 15, 40],
  },
  {
    id: 'TK-1037',
    site: 'north',
    title: 'Нарушение правил переноса груза',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '14:10:07',
    severity: 'info',
    type: 'person',
    description: 'Работник переносит крупногабаритный груз, перекрывающий обзор.',
    action: 'Организуйте перенос груза с помощью тележки.',
    image: 'warehouse',
    contact: warehouse,
    status: 'new',
    box: [66, 43, 12, 17],
  },
  {
    id: 'TK-1036',
    site: 'north',
    title: 'Бег рядом с оборудованием',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '13:58:20',
    severity: 'warning',
    type: 'person',
    description: 'Зафиксировано быстрое перемещение работника в рабочей зоне станков.',
    action: 'Провести разъяснение правил безопасного перемещения.',
    image: 'workshop',
    contact: master,
    status: 'resolved',
    box: [63, 43, 9, 32],
  },
  {
    id: 'TK-1035',
    site: 'north',
    title: 'Падение сотрудника',
    zone: 'Цех № 1',
    camera: 'CAM-01',
    time: '13:41:12',
    severity: 'critical',
    type: 'person',
    description: 'Зафиксировано падение и отсутствие движения в течение 20 секунд. Медицинская помощь оказана, сотрудник в безопасности.',
    action: 'Проверьте акт оказания помощи и состояние участка.',
    image: 'workshop',
    contact: {
      ...master,
      name: 'Анна Белова',
      role: 'Дежурный медработник',
      radio: 'Канал 5 · Медпункт',
      phone: '+7 (495) 555-01-20, доб. 103',
    },
    status: 'resolved',
    box: [37, 65, 28, 18],
  },
]

export const cameras: Camera[] = [
  {
    id: 'CAM-01',
    name: 'Сборочный участок',
    zone: 'Цех № 1',
    workshop: 'Корпус А',
    site: 'north',
    image: 'construction',
    video: '/videos/construction_safety.mp4',
    event: 'TK-1048',
    online: true,
    cameraType: 'visible',
  },
  {
    id: 'THERMAL-OSF-TEST',
    name: 'Тепловизор · тест OSF',
    zone: 'Цех № 1',
    workshop: 'Корпус А',
    site: 'north',
    image: 'workshop',
    online: true,
    cameraType: 'thermal',
  },
]

export const statusLabels: Record<EventStatus, string> = {
  new: 'Новое',
  working: 'В работе',
  resolved: 'Устранено',
  dismissed: 'Ложное срабатывание',
}

export const DEFAULT_MODEL_RULES = [
  'Контроль касок и жилетов (СИЗ)',
  'Опасное сближение с техникой',
  'Нахождение в опасной зоне',
  'Падение человека',
  'Температурный контроль и перегрев',
]

export const zoneRules: Record<string, string[]> = {
  'Цех № 1': DEFAULT_MODEL_RULES,
}
