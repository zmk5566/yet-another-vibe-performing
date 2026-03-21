import("stdfaust.lib");

freq = hslider("freq", 120, 40, 300, 1);
decay = hslider("decay", 0.25, 0.05, 1.0, 0.01);
trigger = button("trigger");

envelope = trigger : en.ar(0.001, decay);
pitch_env = envelope * 5 + 1;
process = os.osc(freq * pitch_env) * envelope * 0.5;
