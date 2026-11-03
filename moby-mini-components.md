# Moby Mini komponentlari

Yig‘ilgan sahna millimetr masshtabida. Sochilgan sahnada simlarning uchlari kontaktlarda qoladi, sim yo‘llari esa qismlarni ko‘rsatish uchun yoyilgan.

| Ref | Tanlangan komponent | 3D manbasi |
| --- | --- | --- |
| U1 | VCC-GND YD-ESP32-S3 N16R8, UART va native USB-C | 57,15 × 27,94 mm plata, ikkita USB-C ulagichi va ikkita 22 kontaktli kolodka Blender generatorida modellashtirilgan. [Ishlab chiqaruvchi va P1/P2 kontaktlari](https://github.com/vcc-gnd/YD-ESP32-S3) |
| M1 | LCDwiki MC096VX, SSD1306 0,96″, 128×64 | PartReel STEP, CC BY 4.0. 27,3 × 27,8 mm plata va 21,74 × 10,86 mm aktiv ekran. [CAD](https://partreel.com/p/ssd1306_module_096/) |
| M2 | INMP441, Ø14 mm olti kontaktli modul | Modul chizmasi va 4,72 × 3,76 × 1 mm TDK paketidan qayta chizilgan. Akustik teshik, silikon kanal va oltita kontakt alohida. [Modul chizmasi](https://ardustore.dk/wp-content/uploads/2026/04/INMP441-Digital-I2C-Mikrofon-Module-Datasheet.pdf) · [TDK](https://product.tdk.com/system/files/dam/doc/product/sw_piezo/mic/mems-mic/data_sheet/inmp441.pdf) |
| S1 | C&K JS202011CQN DPDT | Ishlab chiqaruvchi chizmasidan qayta chizilgan. A va B kontakt guruhlari nomlangan. [Chizma](https://www.farnell.com/datasheets/1851186.pdf) |
| SW1 | 6 mm tactile tugma, 4,3 mm balandlik | KiCad STEP, Omron B3F-1000 gabaritiga mos. Diagonal kontakt jufti ishlatilgan. [CAD](https://kicad.github.io/packages3d/Button_Switch_THT.html) |
| M3 | Adafruit 3006 MAX98357A | 19,4 × 17,8 mm plata va ikki kontaktli vintli terminal Blender generatorida modellashtirilgan. [O‘lchamlar](https://www.adafruit.com/product/3006) · [Kontaktlar](https://learn.adafruit.com/adafruit-max98357-i2s-class-d-mono-amp/pinouts) |
| LS1 | Same Sky CMS-28528N-L152, 8 Ω, 2 W | Ishlab chiqaruvchi chizmasidan qayta chizilgan. Ø28 × 5,2 mm, 32 mm montaj oralig‘i. [Chizma](https://www.sameskydevices.com/product/resource/cms-28528n-l152.pdf) |
| M4 | TowerPro SG90 9 g | Gafeju, FreeCAD Library STEP. O‘rnatish teshiklari va chiqish o‘qi shu modeldan o‘lchangan. [CAD](https://github.com/FreeCAD/FreeCAD-library/tree/master/Electrical%20Parts/Servos/SG-90) |
| C4, C5 | Panasonic EEU-FR1A471, 470 µF, 10 V | Ø8 mm radial korpus, 3,5 mm oyoq oralig‘i. [Chizma](https://media.digikey.com/pdf/Data%20Sheets/Panasonic%20Electronic%20Components/EEU-FR_Series.pdf) |
| LED1, LED2, R1–R7, C1–C2, D1 | 3 mm LED, 0805 rezistor, keramik kondensator, 1N5819 | Standart korpuslar va nomlangan kontaktlar. |

Uchinchi tomon STEP va mesh fayllarining litsenziyalari [THIRD_PARTY.md](THIRD_PARTY.md) faylida ko‘rsatilgan.

## Ulanish va yig‘ish

- [Kontaktlar jadvali](moby-mini-netlist.csv) 22 tarmoqdagi 69 kontaktning yig‘ilgan sahnadagi X, Y va Z koordinatalarini beradi. Har bir sim obyektida `Net`, `From` va `To` xususiyatlari bor.
- S1 ning ikkita OFF kontakti va M3 ning GAIN hamda SD kontaktlari ochiq. D1 tashqi servo quvvati varianti sifatida sochilgan sahnada alohida. Dinamikning ikkala terminali M3 chiqishiga boradi.
- Oyoqlar ichki tirgaklarga birikadi. SG90 va chap koaksial pin qobiqni tayanchlarga nisbatan qiyshaytirish uchun joylashtirilgan. Korpus ichida lehimlanadigan simlar va passivlar uchun tashuvchi plata bor.
- Ishlab chiqarish tolerantligi, sim uzunligi, servo yurishi, USB-C kabel kallagi va quvvat fizik prototipda tekshiriladi.
