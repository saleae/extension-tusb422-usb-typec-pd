from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, StringSetting, NumberSetting, ChoicesSetting
import registers

TUSB422_I2C_ADDRESS = 0x20


class Hla(HighLevelAnalyzer):
    result_types = {
        'set_register_offset': {
            'format': 'Move to {{data.register_name}} ({{data.register}})'
        },
        'write': {
            'format': '[WRITE] {{data.register_name}} = 0b{{bin data.value}}'
        },
        'read': {
            'format': '[READ] {{data.register_name}} == 0b{{bin data.value}}'
        },
    }

    def __init__(self):
        self.process_func = self.process()
        self.process_func.send(None)

    def process(self):
        frame: AnalyzerFrame = yield

        pending_frame: AnalyzerFrame = None

        # If not explicitly written, reads start at register 0
        cur_register_subaddress = 0
        while True:
            while True:
                # Idle, waiting for start
                while frame.type != 'start':
                    frame = yield pending_frame
                    pending_frame = None

                frame = yield
                if frame.type != 'address':
                    frame = yield AnalyzerFrame('error', frame.start_time, frame.end_time)
                    break
                elif frame.data['address'][0] != TUSB422_I2C_ADDRESS:
                    # Not a matching address, break back out to idle
                    break

                is_read = frame.data['read']

                frame = yield
                while frame.type == 'data':
                    if is_read:
                        frame = yield AnalyzerFrame('read', frame.start_time, frame.end_time, {
                            'register': cur_register_subaddress,
                            'register_name': registers.get_register_name(cur_register_subaddress),
                            'value': frame.data['data'][0]
                        })
                        cur_register_subaddress += 1
                    else:
                        cur_register_subaddress = frame.data['data'][0]
                        prev_frame = frame
                        frame = yield
                        if frame.type == 'data':
                            frames = [
                                AnalyzerFrame('set_register_offset', prev_frame.start_time, prev_frame.end_time, {
                                    'register': cur_register_subaddress,
                                    'register_name': registers.get_register_name(cur_register_subaddress),
                                })]
                            while frame.type == 'data':
                                frames.append(
                                    AnalyzerFrame('write', frame.start_time, frame.end_time, {
                                        'register': cur_register_subaddress,
                                        'register_name': registers.get_register_name(cur_register_subaddress),
                                        'value': frame.data['data'][0]
                                    }))
                                frame = yield frames
                                frames = []
                                cur_register_subaddress += 1
                        else:
                            cur_register_subaddress = prev_frame.data['data'][0]
                            pending_frame = AnalyzerFrame(
                                'set_register_offset', prev_frame.start_time, prev_frame.end_time, {
                                    'register': cur_register_subaddress,
                                    'register_name': registers.get_register_name(cur_register_subaddress),
                                })

    def decode(self, frame: AnalyzerFrame):
        return self.process_func.send(frame)
