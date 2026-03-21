import("stdfaust.lib");

decay = hslider("decay", 0.15, 0.05, 0.5, 0.01);
tone = hslider("tone", 0.5, 0, 1, 0.01);
trigger = button("trigger");

envelope = trigger : en.ar(0.001, decay);
noise = no.noise : fi.bandpass(2, 1000, 3000);
process = noise * envelope * 0.4;
