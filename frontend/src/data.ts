export type Severity = 'critical' | 'warning' | 'info'
export type EventStatus = 'new' | 'working' | 'resolved' | 'dismissed'
export type SiteId = 'north' | 'south' | 'east'
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
  employee?: { name: string; role: string; number: string; access: string }
  contact: { name: string; role: string; radio: string; phone: string }
  status: EventStatus
  box: [number, number, number, number]
}
export type Camera = {
  id: string
  name: string
  zone: string
  workshop: string
  site: SiteId
  image: string
  event?: string
  online: boolean
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
      { name: 'Корпус А', zones: ['Цех № 1', 'Окрасочный участок'] },
      { name: 'Корпус Б', zones: ['Склад', 'Погрузочная зона'] },
      { name: 'Периметр', zones: ['Проходная', 'Периметр', 'Высотные работы'] },
    ],
  },
  {
    id: 'south',
    name: 'Южная площадка',
    subtitle: 'Логистический терминал',
    workshops: [
      { name: 'Терминал', zones: ['Зона разгрузки', 'Конвейерная линия'] },
      { name: 'КПП', zones: ['Южные ворота', 'Парковка'] },
    ],
  },
  {
    id: 'east',
    name: 'Восточная площадка',
    subtitle: 'Строительный участок',
    workshops: [
      { name: 'Монтажный участок', zones: ['Котлован', 'Монтажная зона'] },
      { name: 'Склад стройматериалов', zones: ['Склад стройматериалов', 'Бытовой городок'] },
    ],
  },
]

export const accounts: Account[] = [
  { id: 'dispatcher', name: 'Александр Козлов', role: 'Диспетчер', note: 'Оператор безопасности', initials: 'АК' },
  { id: 'master', name: 'Алексей Морозов', role: 'Мастер смены', note: 'Корпус А · смена 08:00–20:00', initials: 'АМ' },
  { id: 'director', name: 'Ирина Соколова', role: 'Руководитель', note: 'Служба безопасности', initials: 'ИС' },
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
    image: 'workshop',
    employee: { name: 'Иван Петров', role: 'Оператор станка · Цех № 1', number: '00482', access: 'Доступ разрешён · СКУД в 14:12' },
    contact: master,
    status: 'new',
    box: [63, 43, 9, 32],
  },
  {
    id: 'TK-1047',
    site: 'north',
    title: 'Попытка несанкционированного прохода',
    zone: 'Проходная',
    camera: 'CAM-08',
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
    zone: 'Склад',
    camera: 'CAM-12',
    time: '14:30:16',
    severity: 'warning',
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
    camera: 'CAM-03',
    time: '14:28:51',
    severity: 'warning',
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
    zone: 'Периметр',
    camera: 'CAM-21',
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
    zone: 'Погрузочная зона',
    camera: 'CAM-16',
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
    zone: 'Высотные работы',
    camera: 'CAM-19',
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
    zone: 'Проходная',
    camera: 'CAM-09',
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
    zone: 'Склад',
    camera: 'CAM-14',
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
    camera: 'CAM-02',
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
    zone: 'Погрузочная зона',
    camera: 'CAM-17',
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
    zone: 'Склад',
    camera: 'CAM-13',
    time: '14:10:07',
    severity: 'warning',
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
    camera: 'CAM-04',
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
    camera: 'CAM-05',
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
  {
    id: 'TK-2051',
    site: 'south',
    title: 'Погрузчик без звукового сигнала',
    zone: 'Зона разгрузки',
    camera: 'CAM-31',
    time: '14:18:24',
    severity: 'warning',
    type: 'person',
    description: 'Погрузчик движется по зоне разгрузки без включённого звукового сигнала. Рядом находятся двое работников склада.',
    action: 'Остановите погрузчик и напомните водителю правила движения по территории.',
    image: 'warehouse',
    contact: warehouse,
    status: 'new',
    box: [52, 42, 14, 34],
  },
  {
    id: 'TK-2050',
    site: 'south',
    title: 'Курение на парковке',
    zone: 'Парковка',
    camera: 'CAM-32',
    time: '14:09:46',
    severity: 'warning',
    type: 'person',
    description: 'Зафиксировано курение в необорудованном месте рядом с топливным складом.',
    action: 'Передайте информацию охране и прекратите нарушение.',
    image: 'perimeter',
    contact: security,
    status: 'new',
    box: [63, 43, 9, 32],
  },
  {
    id: 'TK-2049',
    site: 'south',
    title: 'Проход вне турникета',
    zone: 'Южные ворота',
    camera: 'CAM-33',
    time: '14:05:12',
    severity: 'critical',
    type: 'access',
    description: 'Человек проследовал через южные ворота вне линии турникетов. СКУД не зафиксировала проход.',
    action: 'Направьте патруль к южным воротам и проверьте пропускной режим.',
    image: 'gate',
    employee: {
      name: 'Олег Фёдоров',
      role: 'Водитель · ООО «Логистик»',
      number: 'П-0214',
      access: 'В проходе отказано · Проход вне турникета',
    },
    contact: security,
    status: 'new',
    box: [48, 24, 13, 47],
  },
  {
    id: 'TK-2048',
    site: 'east',
    title: 'Работник без каски в котловане',
    zone: 'Котлован',
    camera: 'CAM-41',
    time: '14:22:37',
    severity: 'critical',
    type: 'person',
    description: 'Сотрудник находится на дне котлована без защитной каски и сигнального жилета.',
    action: 'Приостановите работы в котловане до устранения нарушения.',
    image: 'workshop',
    employee: { name: 'Сергей Ким', role: 'Монтажник · ООО «СтройМонтаж»', number: 'П-0338', access: 'Доступ разрешён · СКУД в 13:40' },
    contact: master,
    status: 'new',
    box: [63, 43, 9, 32],
  },
  {
    id: 'TK-2047',
    site: 'east',
    title: 'Ограждение котлована повреждено',
    zone: 'Котлован',
    camera: 'CAM-42',
    time: '13:57:02',
    severity: 'warning',
    type: 'environment',
    description: 'Секция ограждения котлована смещена, открыт доступ к краю выемки.',
    action: 'Восстановите ограждение и перекройте доступ к опасной зоне.',
    image: 'perimeter',
    contact: master,
    status: 'working',
    box: [28, 55, 24, 25],
  },
  {
    id: 'TK-2046',
    site: 'east',
    title: 'Курение в бытовом городке',
    zone: 'Бытовой городок',
    camera: 'CAM-43',
    time: '13:44:29',
    severity: 'warning',
    type: 'person',
    description: 'Курение в необорудованном месте рядом с бытовыми помещениями.',
    action: 'Уведомите охрану и проведите разъяснение.',
    image: 'workshop',
    contact: security,
    status: 'new',
    box: [66, 43, 12, 17],
  },
]

type CameraSeed = Omit<Camera, 'site' | 'workshop'>
const cameraSeeds: CameraSeed[] = [
  { id: 'CAM-01', name: 'Сборочный участок', zone: 'Цех № 1', image: 'workshop', event: 'TK-1048', online: true },
  { id: 'CAM-02', name: 'Линия сборки', zone: 'Цех № 1', image: 'workshop', event: 'TK-1039', online: true },
  { id: 'CAM-03', name: 'Участок станков', zone: 'Цех № 1', image: 'workshop', event: 'TK-1045', online: true },
  { id: 'CAM-04', name: 'Проход между станками', zone: 'Цех № 1', image: 'workshop', event: 'TK-1036', online: true },
  { id: 'CAM-05', name: 'Зона отдыха', zone: 'Цех № 1', image: 'workshop', event: 'TK-1035', online: true },
  { id: 'CAM-12', name: 'Межстеллажный проход', zone: 'Склад', image: 'warehouse', event: 'TK-1046', online: true },
  { id: 'CAM-13', name: 'Зона комплектации', zone: 'Склад', image: 'warehouse', event: 'TK-1037', online: true },
  { id: 'CAM-14', name: 'Стеллажи ЛКМ', zone: 'Склад', image: 'warehouse', event: 'TK-1040', online: true },
  { id: 'CAM-16', name: 'Зона отгрузки', zone: 'Погрузочная зона', image: 'warehouse', event: 'TK-1043', online: true },
  { id: 'CAM-17', name: 'Мостовой кран', zone: 'Погрузочная зона', image: 'workshop', event: 'TK-1038', online: true },
  { id: 'CAM-08', name: 'Центральная проходная', zone: 'Проходная', image: 'gate', event: 'TK-1047', online: true },
  { id: 'CAM-09', name: 'Пост охраны', zone: 'Проходная', image: 'gate', event: 'TK-1041', online: true },
  { id: 'CAM-21', name: 'Северное ограждение', zone: 'Периметр', image: 'perimeter', event: 'TK-1044', online: true },
  { id: 'CAM-19', name: 'Монтажная площадка', zone: 'Высотные работы', image: 'workshop', event: 'TK-1042', online: false },
  { id: 'CAM-31', name: 'Зона разгрузки', zone: 'Зона разгрузки', image: 'warehouse', event: 'TK-2051', online: true },
  { id: 'CAM-32', name: 'Парковка', zone: 'Парковка', image: 'gate', event: 'TK-2050', online: true },
  { id: 'CAM-33', name: 'Южные ворота', zone: 'Южные ворота', image: 'gate', event: 'TK-2049', online: true },
  { id: 'CAM-41', name: 'Котлован · север', zone: 'Котлован', image: 'perimeter', event: 'TK-2048', online: true },
  { id: 'CAM-42', name: 'Котлован · ограждение', zone: 'Котлован', image: 'perimeter', event: 'TK-2047', online: true },
  { id: 'CAM-43', name: 'Бытовой городок', zone: 'Бытовой городок', image: 'workshop', event: 'TK-2046', online: true },
]

const zoneImages: Record<string, string> = {
  'Цех № 1': 'workshop',
  'Окрасочный участок': 'workshop',
  Склад: 'warehouse',
  'Погрузочная зона': 'warehouse',
  Проходная: 'gate',
  Периметр: 'perimeter',
  'Высотные работы': 'workshop',
  'Зона разгрузки': 'warehouse',
  'Конвейерная линия': 'warehouse',
  'Южные ворота': 'gate',
  Парковка: 'gate',
  Котлован: 'perimeter',
  'Монтажная зона': 'workshop',
  'Склад стройматериалов': 'warehouse',
  'Бытовой городок': 'perimeter',
}
const offlineZones = new Set(['Конвейерная линия', 'Монтажная зона'])
const extraCameraNames = ['Обзорный ракурс', 'Рабочая зона', 'Запасной вход', 'Смежный участок']
let cameraCounter = 101

export const cameras: Camera[] = sites.flatMap((site) =>
  site.workshops.flatMap((workshop) =>
    workshop.zones.flatMap((zone) => {
      const seeds = cameraSeeds.filter((camera) => camera.zone === zone)
      const missing = Math.max(0, 4 - seeds.length)
      const extras: CameraSeed[] = Array.from({ length: missing }, (_, index) => ({
        id: `CAM-${cameraCounter++}`,
        name: extraCameraNames[index % extraCameraNames.length],
        zone,
        image: zoneImages[zone] ?? 'workshop',
        online: !(offlineZones.has(zone) && index === 0),
      }))
      return [...seeds, ...extras].map((camera) => ({ ...camera, site: site.id, workshop: workshop.name }))
    })
  )
)

export const statusLabels: Record<EventStatus, string> = {
  new: 'Новое',
  working: 'В работе',
  resolved: 'Устранено',
  dismissed: 'Ложное срабатывание',
}

export const zoneRules: Record<string, string[]> = {
  'Цех № 1': [
    'Контроль касок и респираторов',
    'Опасное сближение с оборудованием',
    'Бег и использование телефона',
    'Падение человека',
    'Лужи и посторонние предметы',
  ],
  'Окрасочный участок': ['Проверка респиратора', 'Контроль ЛКМ и открытого огня', 'Загромождение проходов'],
  Склад: ['Загромождение проходов', 'Курение и открытый огонь', 'Нарушение правил переноса груза', 'Посторонние предметы и разливы'],
  'Погрузочная зона': ['Сближение с движущимся транспортом', 'Проход под подвешенным грузом', 'Пересечение транспортных маршрутов'],
  Проходная: ['Проверка допуска по СКУД', 'Проверка обязательных СИЗ', 'Попытка несанкционированного прохода'],
  Периметр: ['Перелезание через ограждение', 'Проход вне разрешённой точки', 'Нахождение в запретной зоне'],
  'Высотные работы': ['Отсутствие страховочной привязи', 'Пересечение края безопасной площадки', 'Падение человека'],
  'Зона разгрузки': ['Сближение с движущимся транспортом', 'Проход под подвешенным грузом', 'Звуковой сигнал погрузчика'],
  'Конвейерная линия': ['Опасное сближение с оборудованием', 'Бег и использование телефона', 'Загромождение линии'],
  'Южные ворота': ['Проверка допуска по СКУД', 'Проход вне турникета', 'Нахождение в запретной зоне'],
  Парковка: ['Опасное вождение', 'Курение в неположенном месте', 'Посторонние предметы'],
  Котлован: ['Отсутствие ограждения', 'Работа без каски', 'Падение в котлован'],
  'Монтажная зона': ['Нет страховочной привязи', 'Опасная зона крана', 'Падение предметов'],
  'Склад стройматериалов': ['Загромождение проходов', 'Курение и открытый огонь', 'Разливы и посторонние предметы'],
  'Бытовой городок': ['Курение', 'Нарушение режима', 'Посторонние лица'],
}
