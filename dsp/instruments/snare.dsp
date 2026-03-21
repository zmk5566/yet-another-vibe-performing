import("stdfaust.lib");

freq = hslider("freq", 200, 80, 500, 1);
decay = hslider("decay", 0.2, 0.05, 1.0, 0.01);
noise_mix = hslider("noise_mix", 0.7, 0, 1, 0.01);
trigger = button("trigger");

envelope = trigger : en.ar(0.001, decay);
tone = os.osc(freq) * (1 - noise_mix);
noise = no.noise * noise_mix;
process = (tone + noise) * envelope * 0.5;
