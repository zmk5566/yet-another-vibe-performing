import("stdfaust.lib");

decay = hslider("decay", 0.05, 0.01, 0.5, 0.01);
cutoff = hslider("cutoff", 8000, 2000, 16000, 100);
trigger = button("trigger");

envelope = trigger : en.ar(0.001, decay);
process = no.noise : fi.highpass(2, cutoff) * envelope * 0.3;
