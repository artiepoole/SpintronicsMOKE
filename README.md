# Overview
This repositry contains three main GUIs:
- **ArtieLabUI**: A full gui which pulls frames from the camera and enabled synchronisation of the camera and the light source, allowing for the rapid acquisition of difference images based on different incident polarisations, magnetic field control and, eventually, piezo control.
- **LEDDriverUI**: A lamp controller which is meant to be used as a standlone method to enable focussing (and other simple operations) without the need for the camera to be running. This controls a 8-channel LED source from Leistungselektronik JENA GmbH. This actually controls the LED source using an NI DAQ card. This is necessary because there is no front panel operation for this light source. This is also an interface for the LampController class.
- **MagnetDriverUI**: A magnet controller which is used to independantly control the magnet power supply using an NI DAQ card analog in/out connections. This is necessary in order to have a known calibration between supplied power and the resulting field strength. This is also an interface for the MagnetController class.

# Equipment
- Hamamatsu C11440-42U40 scientific CMOS camera
- Lighting and Electronics Jena Luxyr LQ-LED 8-KANAL fibre lamp system
- Evico Magnetics GmbH breakout for NI DAQ PCIe-6321 DAQ card
- Kepco Bipolar Power Supply BOP100-4DL
- Piezosystem jena CV40 3CLE
- Zeiss Scope.A1 and associated optics (polarisers, aperture, crosshair, lenses, etc.)
- Assortment of Evico Magnetics GmbH sample holders, a cryostat and associated cryogenic systems and electromagnets.

# Tools:
- pybind11 and OpenMP were used to write a few image processing functions in c++.
- PyLabLib was used for camera interfacing 
- NIDAQmx was used for the rest since it's all connected to the provided NIDAQ card breakout box.

# Acknowledgements
This was developed at University of Nottingham in collboration with the Spintronics Group, School of Physics and Astronomy.
