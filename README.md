# Overview
This repositry contains three main GUIs:
- **LEDDriverUI**: A lamp controller which is meant to be used as a standlone method to enable focussing (and other simple operations) without the need for the camera to be running. This controls a 8-channel LED source from Leistungselektronik JENA GmbH. This actually controls the LED source using an NI DAQ card. This is necessary because there is no front panel operation for this light source. This is also an interface for the LampController class.
- **MagnetDriverUI**: A magnet controller which is used to independantly control the magnet power supply using an NI DAQ card analog in/out connections. This is necessary in order to have a known calibration between supplied power and the resulting field strength. This is also an interface for the MagnetController class.
- **ArtieLabUI**: A full gui which pulls frames from the camera and enabled synchronisation of the camera and the light source, allowing for the rapid acquisition of difference images based on different incident polarisations, magnetic field control and, eventually, piezo control.

# Acknowledgements 

This was developed at the University of Nottingham in collboration with the Spintronics Group, School of Physics and Astronomy.
